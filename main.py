# ==========================================
# main.py - المشغل الرئيسي لكوكو بوت
# مستر يوسف الصبحي
# ==========================================

import time
import schedule
import urllib3
from datetime import datetime

from config import *
from alrajhi import check_alrajhi_update, get_all_halal, is_halal
from analyzer import analyze_stock, get_stock_price
from trader import get_account_balance, place_order, calculate_pnl
from reporter import send_daily_report

urllib3.disable_warnings()

def print_banner():
    print("""
╔══════════════════════════════════════╗
║       👑 كوكو بوت للتداول الحلال      ║
║         مستر يوسف الصبحي            ║
║   الراجحي ✅ | IBKR ✅ | AI ✅       ║
╚══════════════════════════════════════╝
    """)

def check_and_update_halal():
    """فحص تحديثات قائمة الراجحي"""
    print(f"\n🕌 [{datetime.now().strftime('%H:%M')}] فحص قائمة الراجحي...")
    check_alrajhi_update()

def run_trading_cycle():
    """دورة التداول الرئيسية"""
    now = datetime.now()
    print(f"\n⚡ [{now.strftime('%H:%M')}] بدء دورة التداول...")
    
    # جلب الرصيد الحالي
    balance = get_account_balance()
    if balance == 0:
        balance = TOTAL_BUDGET  # استخدام الميزانية المحددة في الإعدادات
    
    print(f"💰 الرصيد الحالي: {balance:.2f}")
    
    # تحديد الميزانية لكل نوع
    spec_budget  = balance * SPECULATION_RATIO
    invest_budget = balance * INVESTMENT_RATIO
    
    # الأسهم الحلال
    halal = get_all_halal()
    
    # ===== تحليل الأسهم السعودية =====
    print("\n🇸🇦 تحليل السوق السعودي...")
    sa_signals = []
    for ticker in halal['sa'][:5]:  # أول 5 أسهم
        try:
            result = analyze_stock(ticker, ticker, "SA")
            if result['signal'] == 'شراء' and result['confidence'] >= 65:
                sa_signals.append(result)
                print(f"  🟢 {ticker}: شراء ({result['confidence']}%)")
            else:
                print(f"  ⏸️ {ticker}: {result['signal']}")
        except Exception as e:
            print(f"  ⚠️ خطأ في {ticker}: {e}")
        time.sleep(1)
    
    # ===== تحليل الأسهم الأمريكية =====
    print("\n🇺🇸 تحليل السوق الأمريكي...")
    us_signals = []
    for ticker in halal['us'][:5]:  # أول 5 أسهم
        try:
            result = analyze_stock(ticker, ticker, "US")
            if result['signal'] == 'شراء' and result['confidence'] >= 65:
                us_signals.append(result)
                print(f"  🟢 {ticker}: شراء ({result['confidence']}%)")
            else:
                print(f"  ⏸️ {ticker}: {result['signal']}")
        except Exception as e:
            print(f"  ⚠️ خطأ في {ticker}: {e}")
        time.sleep(1)
    
    # ===== تنفيذ الصفقات =====
    executed = 0
    
    # مضاربة - أفضل إشارة سعودية
    if sa_signals and spec_budget > 10:
        best_sa = max(sa_signals, key=lambda x: x['confidence'])
        if best_sa['price'] > 0:
            qty = max(1, int(spec_budget * 0.3 / best_sa['price']))
            result = place_order(
                best_sa['ticker'], best_sa['ticker'],
                'BUY', qty, best_sa['price'], 'SA'
            )
            if result['success']:
                executed += 1
    
    # استثمار - أفضل إشارة أمريكية
    if us_signals and invest_budget > 10:
        best_us = max(us_signals, key=lambda x: x['confidence'])
        if best_us['price'] > 0:
            qty = max(1, int(invest_budget * 0.3 / best_us['price']))
            result = place_order(
                best_us['ticker'], best_us['ticker'],
                'BUY', qty, best_us['price'], 'US'
            )
            if result['success']:
                executed += 1
    
    pnl = calculate_pnl()
    print(f"\n📊 ملخص الدورة:")
    print(f"  ✅ صفقات منفذة: {executed}")
    print(f"  💰 ربح/خسارة اليوم: {pnl['pnl']:.2f} ر.س")

def send_report():
    """إرسال التقرير اليومي"""
    print(f"\n📤 [{datetime.now().strftime('%H:%M')}] إرسال التقرير اليومي...")
    send_daily_report()

def setup_schedule():
    """إعداد الجدول الزمني"""
    # فحص الراجحي كل يوم الساعة 9 صباحاً
    schedule.every().day.at(f"{CHECK_ALRAJHI_HOUR:02d}:00").do(check_and_update_halal)
    
    # دورة تداول كل ساعة خلال أوقات السوق
    schedule.every().hour.do(run_trading_cycle)
    
    # تقرير يومي الساعة 11 مساءً
    schedule.every().day.at(f"{REPORT_HOUR:02d}:{REPORT_MINUTE:02d}").do(send_report)
    
    print("""
⏰ الجدول الزمني:
  • 09:00 - فحص قائمة الراجحي
  • كل ساعة - دورة التداول
  • 23:00 - التقرير اليومي
    """)

def main():
    print_banner()
    print(f"🚀 بدء تشغيل كوكو بوت...")
    print(f"💰 الميزانية: {TOTAL_BUDGET} ر.س")
    print(f"📈 المضاربة: {SPECULATION_RATIO*100:.0f}% | الاستثمار: {INVESTMENT_RATIO*100:.0f}%")
    print(f"🎯 هدف الربح: {PROFIT_TARGET*100:.0f}% | حد الخسارة: {STOP_LOSS*100:.0f}%")
    print(f"📊 الحساب: {'🧪 تجريبي' if IBKR_ACCOUNT=='paper' else '💰 حقيقي'}")
    
    # فحص أولي للراجحي
    check_and_update_halal()
    
    # دورة تداول أولية
    run_trading_cycle()
    
    # إعداد الجدول
    setup_schedule()
    
    print("\n✅ البوت يعمل الآن! اضغط Ctrl+C للإيقاف\n")
    
    # الحلقة الرئيسية
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
