# ==========================================
# reporter.py - مرسل التقارير اليومية
# ==========================================

import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import *
from trader import get_today_trades, calculate_pnl

def build_report():
    """بناء التقرير اليومي"""
    trades = get_today_trades()
    pnl    = calculate_pnl()
    now    = datetime.now().strftime("%A %d/%m/%Y")
    
    report = f"""
👑 مستر يوسف الصبحي
📊 التقرير اليومي - {now}

💰 ملخص اليوم:
• إجمالي المشتريات: {pnl['bought']:.2f} ر.س
• إجمالي المبيعات: {pnl['sold']:.2f} ر.س
• {'🟢 ربح' if pnl['pnl'] >= 0 else '🔴 خسارة'}: {abs(pnl['pnl']):.2f} ر.س

📋 الصفقات ({len(trades)} صفقة):
"""
    for t in trades:
        emoji = "🟢" if t['action'] == 'BUY' else "🔴"
        action = "شراء" if t['action'] == 'BUY' else "بيع"
        report += f"{emoji} {action} {t['name']} × {t['quantity']} بـ {t['price']:.2f}\n"
    
    if not trades:
        report += "• لا توجد صفقات اليوم\n"
    
    report += f"""
🕌 جميع الأسهم من قائمة الراجحي الحلال ✅
⚙️ هدف الربح: {PROFIT_TARGET*100:.0f}% | حد الخسارة: {STOP_LOSS*100:.0f}%

🤖 كوكو بوت - تداول حلال ذكي
    """
    return report.strip()

def send_email(report):
    """إرسال التقرير بالإيميل"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"📊 تقريرك اليومي - مستر يوسف - {datetime.now().strftime('%d/%m/%Y')}"
        msg['From']    = EMAIL_SENDER
        msg['To']      = EMAIL_RECEIVER
        
        # نص عادي
        msg.attach(MIMEText(report, 'plain', 'utf-8'))
        
        # HTML جميل
        html = f"""
        <div dir="rtl" style="font-family:Arial;max-width:600px;margin:auto;background:#0a0e1a;color:#e8eaf6;padding:20px;border-radius:15px">
            <h2 style="color:#f0b429;text-align:center">👑 مستر يوسف الصبحي</h2>
            <pre style="background:#151d35;padding:15px;border-radius:10px;color:#e8eaf6;white-space:pre-wrap">{report}</pre>
            <p style="color:#6b7ab8;text-align:center;font-size:12px">🤖 كوكو بوت - تداول حلال ذكي</p>
        </div>
        """
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        
        print("✅ تم إرسال التقرير بالإيميل")
        return True
    except Exception as e:
        print(f"⚠️ خطأ في إرسال الإيميل: {e}")
        return False

def send_telegram(report):
    """إرسال التقرير بالتيليجرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": report,
            "parse_mode": "HTML"
        }, timeout=30)
        if response.status_code == 200:
            print("✅ تم إرسال التقرير بالتيليجرام")
            return True
    except Exception as e:
        print(f"⚠️ خطأ في إرسال التيليجرام: {e}")
    return False

def send_whatsapp(report):
    """إرسال التقرير بالواتساب عبر Infobip"""
    try:
        response = requests.post(
            "https://api.infobip.com/whatsapp/1/message/text",
            headers={
                "Authorization": f"App {INFOBIP_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": "447860099299",
                "to": INFOBIP_PHONE,
                "content": {"text": report}
            },
            timeout=30
        )
        if response.status_code == 200:
            print("✅ تم إرسال التقرير بالواتساب")
            return True
    except Exception as e:
        print(f"⚠️ خطأ في إرسال الواتساب: {e}")
    return False

def send_daily_report():
    """إرسال التقرير اليومي على كل القنوات"""
    print("📤 جاري إرسال التقرير اليومي...")
    report = build_report()
    
    email_ok    = send_email(report)
    telegram_ok = send_telegram(report)
    whatsapp_ok = send_whatsapp(report)
    
    print(f"""
📊 نتيجة الإرسال:
• إيميل: {'✅' if email_ok else '❌'}
• تيليجرام: {'✅' if telegram_ok else '❌'}
• واتساب: {'✅' if whatsapp_ok else '❌'}
    """)
    return report

if __name__ == "__main__":
    send_daily_report()
