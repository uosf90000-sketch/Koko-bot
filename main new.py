# ==========================================
# main.py - كوكو بوت - مستر يوسف الصبحي
# ==========================================

import os
import time
import json
import schedule
import threading
import urllib3
from datetime import datetime

urllib3.disable_warnings()

# ====== إعدادات من Railway Variables ======
IBKR_USERNAME    = os.environ.get('IBKR_USERNAME', '')
IBKR_PASSWORD    = os.environ.get('IBKR_PASSWORD', '')
IBKR_ACCOUNT     = os.environ.get('IBKR_ACCOUNT', 'paper')
TOTAL_BUDGET     = float(os.environ.get('TOTAL_BUDGET', '100'))
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
EMAIL_SENDER     = os.environ.get('EMAIL_SENDER', '')
EMAIL_PASSWORD   = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_RECEIVER   = os.environ.get('EMAIL_RECEIVER', '')
GEMINI_API_KEY   = os.environ.get('GEMINI_API_KEY', '')
GROQ_API_KEY     = os.environ.get('GROQ_API_KEY', '')

SPECULATION_RATIO = 0.60
INVESTMENT_RATIO  = 0.40
PROFIT_TARGET     = 0.20
STOP_LOSS         = 0.05

import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from api import start_api, add_trade, update_analysis, load_data, save_data

# ====== قائمة الأسهم الحلال ======
HALAL_SA = [
    {"ticker":"2222","name":"أرامكو","emoji":"🛢️"},
    {"ticker":"1211","name":"معادن","emoji":"⛏️"},
    {"ticker":"4013","name":"جرير","emoji":"📱"},
    {"ticker":"7010","name":"STC","emoji":"📡"},
    {"ticker":"1010","name":"الرياض","emoji":"🏛️"},
]
HALAL_US = [
    {"ticker":"MSFT","name":"مايكروسوفت","emoji":"💻"},
    {"ticker":"AAPL","name":"آبل","emoji":"🍎"},
    {"ticker":"GOOG","name":"جوجل","emoji":"🔍"},
    {"ticker":"AMZN","name":"أمازون","emoji":"📦"},
    {"ticker":"NVDA","name":"انفيديا","emoji":"🎮"},
]

def print_banner():
    print("""
╔══════════════════════════════════════╗
║    👑 كوكو بوت - مستر يوسف الصبحي   ║
╚══════════════════════════════════════╝
    """)
    print(f"💰 الميزانية: {TOTAL_BUDGET} ر.س")
    print(f"🤖 Gemini: {'✅' if GEMINI_API_KEY else '❌'}")
    print(f"⚡ Groq: {'✅' if GROQ_API_KEY else '❌'}")
    print(f"📲 تيليجرام: {'✅' if TELEGRAM_TOKEN else '❌'}")

def get_stock_price(ticker, market="US"):
    try:
        import yfinance as yf
        t = ticker + ".SR" if market == "SA" else ticker
        stock = yf.Ticker(t)
        hist = stock.history(period="5d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            prev  = hist['Close'].iloc[-2] if len(hist) > 1 else price
            change = ((price - prev) / prev) * 100
            return {"price": round(price, 2), "change": round(change, 2)}
    except Exception as e:
        print(f"⚠️ خطأ {ticker}: {e}")
    return {"price": 0, "change": 0}

def analyze_gemini(ticker, price, change):
    if not GEMINI_API_KEY: return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        prompt = f'حلل سهم {ticker} السعر:{price} التغير:{change}%. أجب بـ JSON فقط: {{"signal":"شراء أو احتفظ أو بيع","confidence":50}}'
        r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=20)
        if r.status_code == 200:
            text = r.json()['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text.replace("```json","").replace("```","").strip())
    except: pass
    return None

def analyze_groq(ticker, price, change):
    if not GROQ_API_KEY: return None
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model":"llama3-8b-8192","messages":[
                {"role":"system","content":"أجب بـ JSON فقط"},
                {"role":"user","content":f'حلل {ticker} السعر:{price} التغير:{change}%\n{{"signal":"شراء أو احتفظ أو بيع","confidence":50}}'}
            ],"max_tokens":100}, timeout=20
        )
        if r.status_code == 200:
            text = r.json()['choices'][0]['message']['content']
            return json.loads(text.replace("```json","").replace("```","").strip())
    except: pass
    return None

def vote(results):
    votes = {"شراء":0,"احتفظ":0,"بيع":0}
    conf = 0; valid = 0
    for r in results:
        if r and r.get('signal') in votes:
            votes[r['signal']] += 1
            conf += r.get('confidence', 50)
            valid += 1
    winner = max(votes, key=votes.get)
    return winner, round(conf/valid) if valid else 50

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=20)
        print("✅ تيليجرام أُرسل")
    except Exception as e:
        print(f"⚠️ تيليجرام: {e}")

def send_email_report(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD: return
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

trades_today = []

def run_trading_cycle():
    global trades_today
    print(f"\n⚡ [{datetime.now().strftime('%H:%M')}] دورة تداول...")
    analyses = []

    for stock in HALAL_US[:3]:
        data = get_stock_price(stock['ticker'], "US")
        if data['price'] == 0: continue

        r1 = analyze_gemini(stock['ticker'], data['price'], data['change'])
        r2 = analyze_groq(stock['ticker'], data['price'], data['change'])
        signal, conf = vote([r1, r2])

        analysis = {
            "ticker": stock['ticker'],
            "name": stock['name'],
            "price": data['price'],
            "change": data['change'],
            "signal": signal,
            "confidence": conf,
            "market": "US"
        }
        analyses.append(analysis)
        print(f"  {stock['ticker']}: {signal} ({conf}%)")

        if signal == "شراء" and conf >= 60:
            trade_msg = f"👑 مستر يوسف!\n✅ شراء {stock['emoji']} {stock['name']}\nالسعر: ${data['price']:.2f}\nثقة AI: {conf}%\n🕌 سهم حلال ✓"
            send_telegram(trade_msg)
            add_trade(stock['ticker'], stock['name'], "شراء", data['price'], "US")
            trades_today.append(f"✅ شراء {stock['name']} ${data['price']:.2f}")

        time.sleep(2)

    update_analysis(analyses)
    
    # تحديث حالة البوت
    bot_data = load_data()
    bot_data["status"] = "running"
    bot_data["buy_signals_today"] = sum(1 for a in analyses if a['signal'] == 'شراء')
    save_data(bot_data)

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
    send_email_report(f"📊 تقريرك اليومي - {now}", report)
    trades_today = []
    print("📤 التقرير اليومي أُرسل")

def main():
    print_banner()

    # تشغيل API في thread منفصل
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # رسالة ترحيب
    send_telegram("""👑 مرحباً مستر يوسف!

🤖 كوكو بوت بدأ يشتغل!
💰 الميزانية: 100 ر.س
🕌 أسهم حلال من الراجحي
⏰ تقرير كل ليلة 11
📊 لوحة التحكم متاحة!

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
