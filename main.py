import os
import json
import time
import schedule
import threading
import urllib3
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO

urllib3.disable_warnings()

# ====== إعدادات ======
TOTAL_BUDGET     = float(os.environ.get('TOTAL_BUDGET', '100'))
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
EMAIL_SENDER     = os.environ.get('EMAIL_SENDER', '')
EMAIL_PASSWORD   = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_RECEIVER   = os.environ.get('EMAIL_RECEIVER', '')
GEMINI_API_KEY   = os.environ.get('GEMINI_API_KEY', '')
GROQ_API_KEY     = os.environ.get('GROQ_API_KEY', '')
ALPACA_KEY       = os.environ.get('ALPACA_KEY', '')
ALPACA_SECRET    = os.environ.get('ALPACA_SECRET', '')
ALPACA_BASE_URL  = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
PORT             = int(os.environ.get('PORT', 8080))

import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ====== بيانات مشتركة ======
BOT_DATA = {
    "status": "running",
    "balance": "balance": get_alpaca_balance(),
    "trades": [],
    "last_analysis": [],
    "stats": {"total_trades": 0, "buy_signals": 0},
    "buy_signals_today": 0,
    "updated": str(datetime.now())
}

# ====== API Server ======
class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        BOT_DATA["updated"] = str(datetime.now())
        self.wfile.write(json.dumps(BOT_DATA, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def log_message(self, format, *args):
        pass

def start_api():
    server = HTTPServer(('0.0.0.0', PORT), APIHandler)
    print(f"✅ API شغّال على port {PORT}")
    server.serve_forever()

# ====== أسهم حلال ======
HALAL_US = [
    {"ticker": "MSFT", "name": "مايكروسوفت", "emoji": "💻"},
    {"ticker": "NVDA", "name": "انفيديا", "emoji": "🎮"},
    {"ticker": "GOOG", "name": "جوجل", "emoji": "🔍"},
    {"ticker": "AAPL", "name": "آبل", "emoji": "🍎"},
    {"ticker": "AMZN", "name": "أمازون", "emoji": "📦"},
]

# ====== Alpaca API ======
ALPACA_HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

def get_alpaca_price(ticker):
    """جلب السعر من Alpaca"""
    try:
        url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars?timeframe=1Day&limit=5"
        r = requests.get(url, headers=ALPACA_HEADERS, timeout=15)
        if r.status_code == 200:
            bars = r.json().get('bars', [])
            if len(bars) >= 2:
                price = bars[-1]['c']
                prev = bars[-2]['c']
                change = ((price - prev) / prev) * 100
                return round(price, 2), round(change, 2)
    except Exception as e:
        print(f"⚠️ Alpaca سعر {ticker}: {e}")
    return 0, 0

def get_alpaca_balance():
    """جلب الرصيد من Alpaca"""
    try:
        url = f"{ALPACA_BASE_URL}/v2/account"
        r = requests.get(url, headers=ALPACA_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return float(data.get('cash', TOTAL_BUDGET))
    except Exception as e:
        print(f"⚠️ Alpaca رصيد: {e}")
    return TOTAL_BUDGET

def place_alpaca_order(ticker, qty, side="buy"):
    """تنفيذ صفقة في Alpaca"""
    try:
        url = f"{ALPACA_BASE_URL}/v2/orders"
        order = {
            "symbol": ticker,
            "qty": qty,
            "side": side,
            "type": "market",
            "time_in_force": "day"
        }
        r = requests.post(url, headers=ALPACA_HEADERS, json=order, timeout=15)
        if r.status_code in [200, 201]:
            print(f"✅ تم تنفيذ {side} {qty} سهم من {ticker}")
            return True, r.json()
        else:
            print(f"⚠️ خطأ في الأمر: {r.text}")
    except Exception as e:
        print(f"⚠️ Alpaca أمر: {e}")
    return False, None

# ====== جلب الأسعار ======
def get_price(ticker):
    price, change = get_alpaca_price(ticker)
    if price > 0:
        return price, change
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
            closes = [c for c in closes if c is not None]
            if len(closes) >= 2:
                price = closes[-1]
                prev = closes[-2]
                change = ((price - prev) / prev) * 100
                return round(price, 2), round(change, 2)
    except Exception as e:
        print(f"⚠️ Yahoo {ticker}: {e}")
    return 0, 0

# ====== Gemini ======
def analyze_gemini(ticker, price, change):
    if not GEMINI_API_KEY:
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        prompt = f'حلل {ticker} السعر:{price} التغير:{change}%. JSON فقط: {{"signal":"شراء أو احتفظ أو بيع","confidence":70}}'
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if r.status_code == 200:
            text = r.json()['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text.replace("```json","").replace("```","").strip())
    except:
        pass
    return None

# ====== Groq ======
def analyze_groq(ticker, price, change):
    if not GROQ_API_KEY:
        return None
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": "أجب بـ JSON فقط"},
                    {"role": "user", "content": f'حلل {ticker} السعر:{price} التغير:{change}%\n{{"signal":"شراء أو احتفظ أو بيع","confidence":70}}'}
                ],
                "max_tokens": 100
            }, timeout=20
        )
        if r.status_code == 200:
            text = r.json()['choices'][0]['message']['content']
            return json.loads(text.replace("```json","").replace("```","").strip())
    except:
        pass
    return None

# ====== تصويت ======
def vote(results):
    votes = {"شراء": 0, "احتفظ": 0, "بيع": 0}
    conf = 0
    valid = 0
    for r in results:
        if r and r.get('signal') in votes:
            votes[r['signal']] += 1
            conf += r.get('confidence', 50)
            valid += 1
    winner = max(votes, key=votes.get)
    return winner, round(conf / valid) if valid else 50

# ====== تيليجرام ======
def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=20
        )
        if r.status_code == 200:
            print("✅ تيليجرام أُرسل")
    except Exception as e:
        print(f"⚠️ تيليجرام: {e}")

def send_telegram_pdf(pdf_bytes, filename):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not pdf_bytes:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": "👑 تقريرك اليومي PDF"},
            files={"document": (filename, pdf_bytes, "application/pdf")},
            timeout=30
        )
        if r.status_code == 200:
            print("✅ PDF تيليجرام أُرسل")
    except Exception as e:
        print(f"⚠️ PDF: {e}")

# ====== إيميل ======
def send_email_with_pdf(subject, body, pdf_bytes, filename):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        if pdf_bytes:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(part)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("✅ إيميل أُرسل")
    except Exception as e:
        print(f"⚠️ إيميل: {e}")

# ====== PDF ======
def create_pdf(trades, analyses):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('T', parent=styles['Normal'], fontSize=18, fontName='Helvetica-Bold',
                                     textColor=colors.HexColor('#f5c842'), alignment=TA_CENTER, spaceAfter=8)
        sub_style = ParagraphStyle('S', parent=styles['Normal'], fontSize=11, fontName='Helvetica',
                                   textColor=colors.HexColor('#888888'), alignment=TA_CENTER, spaceAfter=15)

        now = datetime.now()
        story.append(Paragraph("KOKO TRADER BOT", title_style))
        story.append(Paragraph(f"Mr. Yousef Alsubhi | {now.strftime('%d/%m/%Y %H:%M')}", sub_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#f5c842')))
        story.append(Spacer(1, 15))

        # ملخص
        story.append(Paragraph("DAILY SUMMARY", title_style))
        summary = [
            ['Item', 'Value'],
            ['Budget', f'{TOTAL_BUDGET} SAR'],
            ['Trades Today', str(len(trades))],
            ['Platform', 'Alpaca Paper Trading'],
            ['Halal Filter', '0% Purification'],
        ]
        t = Table(summary, colWidths=[250, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f5c842')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f9f9f9'), colors.white]),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

        # تحليل
        if analyses:
            story.append(Paragraph("AI ANALYSIS", title_style))
            ai_data = [['Stock', 'Price', 'Change', 'Signal', 'Confidence']]
            for a in analyses:
                ai_data.append([a['ticker'], f"${a['price']:.2f}", f"{'+' if a['change']>=0 else ''}{a['change']:.1f}%", a['signal'], f"{a['confidence']}%"])
            at = Table(ai_data, colWidths=[80, 90, 80, 80, 90])
            at.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2dd4ff')),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f0f8ff'), colors.white]),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(at)
            story.append(Spacer(1, 20))

        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#f5c842')))
        story.append(Spacer(1, 10))
        story.append(Paragraph("Halal Certified | Al-Rajhi List | KOKO BOT", sub_style))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        print(f"⚠️ PDF: {e}")
        return None

# ====== دورة التداول ======
trades_today = []

def run_trading_cycle():
    global trades_today
    print(f"\n⚡ [{datetime.now().strftime('%H:%M')}] دورة تداول...")

    # جلب الرصيد
    balance = get_alpaca_balance()
    BOT_DATA["balance"] = balance
    print(f"💰 الرصيد: ${balance:.2f}")

    analyses = []
    buy_count = 0
    budget_per_trade = balance * 0.1  # 10% لكل صفقة

    for stock in HALAL_US[:3]:
        price, change = get_price(stock['ticker'])
        if price == 0:
            continue

        r1 = analyze_gemini(stock['ticker'], price, change)
        r2 = analyze_groq(stock['ticker'], price, change)
        signal, conf = vote([r1, r2])

        analysis = {
            "ticker": stock['ticker'],
            "name": stock['name'],
            "price": price,
            "change": change,
            "signal": signal,
            "confidence": conf
        }
        analyses.append(analysis)
        print(f"  {stock['ticker']}: {signal} ({conf}%)")

        if signal == "شراء" and conf >= 65 and price > 0:
            qty = max(1, int(budget_per_trade / price))
            success, order = place_alpaca_order(stock['ticker'], qty, "buy")

            if success:
                buy_count += 1
                msg = f"👑 مستر يوسف!\n✅ تم شراء {stock['emoji']} {stock['name']}\nالكمية: {qty} سهم\nالسعر: ${price:.2f}\nثقة: {conf}%\n🕌 حلال ✓\n📊 Alpaca Paper"
                send_telegram(msg)
                trade = {
                    "ticker": stock['ticker'],
                    "name": stock['name'],
                    "action": "شراء",
                    "price": price,
                    "qty": qty,
                    "timeStr": datetime.now().strftime("%H:%M:%S"),
                    "time": str(datetime.now())
                }
                BOT_DATA["trades"].insert(0, trade)
                BOT_DATA["trades"] = BOT_DATA["trades"][:50]
                BOT_DATA["stats"]["total_trades"] += 1
                trades_today.append(f"✅ شراء {qty} {stock['name']} @ ${price:.2f}")

        time.sleep(2)

    BOT_DATA["last_analysis"] = analyses
    BOT_DATA["buy_signals_today"] = buy_count

# ====== تقرير ليلي ======
def send_daily_report():
    global trades_today
    now = datetime.now().strftime("%d/%m/%Y")
    filename = f"koko_report_{datetime.now().strftime('%Y%m%d')}.pdf"

    body = f"""👑 مستر يوسف الصبحي
📊 التقرير اليومي - {now}

💰 الرصيد: ${BOT_DATA['balance']:.2f}
📈 الصفقات: {len(trades_today)}

{chr(10).join(trades_today) if trades_today else 'لا توجد صفقات اليوم'}

🕌 كل الأسهم حلال ✅
📊 منصة Alpaca Paper Trading
🤖 كوكو بوت"""

    pdf_bytes = create_pdf(trades_today, BOT_DATA.get("last_analysis", []))
    send_telegram(body)
    if pdf_bytes:
        send_telegram_pdf(pdf_bytes, filename)
        send_email_with_pdf(f"📊 تقريرك اليومي PDF - {now}", body, pdf_bytes, filename)

    trades_today = []
    print("📤 التقرير اليومي أُرسل")

# ====== Main ======
def main():
    print("👑 كوكو بوت - مستر يوسف الصبحي")
    print(f"📊 Alpaca: {'✅' if ALPACA_KEY else '❌'}")

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    time.sleep(2)

    send_telegram("""👑 مرحباً مستر يوسف!

🤖 كوكو بوت بدأ يشتغل!
📊 منصة Alpaca Paper Trading
🕌 أسهم حلال من الراجحي
⏰ تقرير PDF كل ليلة 11
🚀 البوت جاهز!""")

    run_trading_cycle()

    schedule.every().hour.do(run_trading_cycle)
    schedule.every().day.at("23:00").do(send_daily_report)

    print("✅ البوت يعمل 24/7!")

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
