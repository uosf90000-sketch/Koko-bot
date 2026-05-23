import os
import json
import time
import schedule
import threading
import urllib3
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

urllib3.disable_warnings()

# ====== إعدادات ======
IBKR_ACCOUNT     = os.environ.get('IBKR_ACCOUNT', 'paper')
TOTAL_BUDGET     = float(os.environ.get('TOTAL_BUDGET', '100'))
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
EMAIL_SENDER     = os.environ.get('EMAIL_SENDER', '')
EMAIL_PASSWORD   = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_RECEIVER   = os.environ.get('EMAIL_RECEIVER', '')
GEMINI_API_KEY   = os.environ.get('GEMINI_API_KEY', '')
GROQ_API_KEY     = os.environ.get('GROQ_API_KEY', '')
PORT             = int(os.environ.get('PORT', 8080))

import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ====== بيانات مشتركة ======
BOT_DATA = {
    "status": "running",
    "balance": TOTAL_BUDGET,
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
    {"ticker": "AMZN", "name": "أمازون", "emoji": "📦"},
    {"ticker": "AAPL", "name": "آبل", "emoji": "🍎"},
]

# ====== جلب الأسعار ======
def get_price(ticker):
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2] if len(hist) > 1 else price
            change = ((price - prev) / prev) * 100
            return round(price, 2), round(change, 2)
    except:
        pass
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
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=20
        )
        print("✅ تيليجرام أُرسل")
    except Exception as e:
        print(f"⚠️ تيليجرام: {e}")

# ====== إيميل ======
def send_email(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("✅ إيميل أُرسل")
    except Exception as e:
        print(f"⚠️ إيميل: {e}")

# ====== دورة التداول ======
trades_today = []

def run_trading_cycle():
    global trades_today
    print(f"\n⚡ [{datetime.now().strftime('%H:%M')}] دورة تداول...")
    analyses = []
    buy_count = 0

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

        if signal == "شراء" and conf >= 60:
            buy_count += 1
            msg = f"👑 مستر يوسف!\n✅ شراء {stock['emoji']} {stock['name']}\nالسعر: ${price:.2f}\nثقة: {conf}%\n🕌 حلال ✓"
            send_telegram(msg)
            trade = {
                "ticker": stock['ticker'],
                "name": stock['name'],
                "action": "شراء",
                "price": price,
                "timeStr": datetime.now().strftime("%H:%M:%S"),
                "time": str(datetime.now())
            }
            BOT_DATA["trades"].insert(0, trade)
            BOT_DATA["trades"] = BOT_DATA["trades"][:50]
            BOT_DATA["stats"]["total_trades"] += 1
            trades_today.append(f"✅ شراء {stock['name']} ${price:.2f}")

        time.sleep(2)

    BOT_DATA["last_analysis"] = analyses
    BOT_DATA["buy_signals_today"] = buy_count
    BOT_DATA["stats"]["buy_signals"] = buy_count

# ====== تقرير ليلي ======
def send_daily_report():
    global trades_today
    now = datetime.now().strftime("%d/%m/%Y")
    report = f"""👑 مستر يوسف الصبحي
📊 التقرير اليومي - {now}

💰 الميزانية: {TOTAL_BUDGET} ر.س
📈 الصفقات: {len(trades_today)}

"""
    report += "\n".join(trades_today) if trades_today else "لا توجد صفقات اليوم"
    report += "\n\n🕌 كل الأسهم حلال ✅\n🤖 كوكو بوت"

    send_telegram(report)
    send_email(f"📊 تقريرك اليومي - {now}", report)
    trades_today = []
    print("📤 التقرير اليومي أُرسل")

# ====== Main ======
def main():
    print("""
╔══════════════════════════════════════╗
║    👑 كوكو بوت - مستر يوسف الصبحي   ║
╚══════════════════════════════════════╝
    """)

    # تشغيل API في thread منفصل
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # رسالة ترحيب
    send_telegram("""👑 مرحباً مستر يوسف!

🤖 كوكو بوت بدأ يشتغل!
💰 الميزانية: 100 ر.س
🕌 أسهم حلال من الراجحي
⏰ تقرير كل ليلة 11
📊 اللوحة متاحة!

🚀 البوت جاهز!""")

    # دورة أولى
    run_trading_cycle()

    # جدول زمني
    schedule.every().hour.do(run_trading_cycle)
    schedule.every().day.at("23:00").do(send_daily_report)

    print("\n✅ البوت يعمل 24/7!\n")

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
