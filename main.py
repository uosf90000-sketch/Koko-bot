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
TOTAL_BUDGET     = float(os.environ.get('TOTAL_BUDGET', '100000'))
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

ALPACA_HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

# ====== جلب الرصيد من Alpaca ======
def get_alpaca_balance():
    try:
        url = f"{ALPACA_BASE_URL}/v2/account"
        r = requests.get(url, headers=ALPACA_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            balance = float(data.get('cash', TOTAL_BUDGET))
            print(f"💰 الرصيد من Alpaca: ${balance:.2f}")
            return balance
    except Exception as e:
        print(f"⚠️ خطأ في جلب الرصيد: {e}")
    return TOTAL_BUDGET

# ====== بيانات مشتركة ======
BOT_DATA = {
    "status": "running",
    "balance": get_alpaca_balance(),
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
        BOT_DATA["balance"] = get_alpaca_balance()
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

# ====== جلب الأسعار ======
def get_price(ticker):
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
        print(f"⚠️ خطأ {ticker}: {e}")
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

    balance = get_alpaca_balance()
    BOT_DATA["balance"] = balance
    print(f"💰 الرصيد: ${balance:.2f}")

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

        if signal == "شراء" and conf >= 30:
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

# ====== تقرير ليلي ======
def send_daily_report():
    global trades_today
    now = datetime.now().strftime("%d/%m/%Y")
    balance = get_alpaca_balance()

    report = f"""👑 مستر يوسف الصبحي
📊 التقرير اليومي - {now}

💰 الرصيد: ${balance:.2f}
📈 الصفقات: {len(trades_today)}

"""
    report += "\n".join(trades_today) if trades_today else "لا توجد صفقات اليوم"
    report += "\n\n🕌 كل الأسهم حلال ✅\n📊 Alpaca Paper Trading\n🤖 كوكو بوت"

    send_telegram(report)
    send_email(f"📊 تقريرك اليومي - {now}", report)
    trades_today = []
    print("📤 التقرير اليومي أُرسل")

# ====== Main ======
def main():
    print("👑 كوكو بوت - مستر يوسف الصبحي")

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    time.sleep(2)

    balance = get_alpaca_balance()
    send_telegram(f"""👑 مرحباً مستر يوسف!

🤖 كوكو بوت بدأ يشتغل!
💰 الرصيد: ${balance:.2f}
🕌 أسهم حلال من الراجحي
⏰ تقرير كل ليلة 11
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
