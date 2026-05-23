# ==========================================
# alrajhi.py - فاحص قائمة الراجحي الحلال
# ==========================================

import requests
import json
import os
from datetime import datetime

HALAL_FILE = "halal_stocks.json"

# قائمة أسهم حلال افتراضية (يتم تحديثها من الراجحي)
DEFAULT_HALAL_SA = [
    "2222",  # أرامكو
    "1211",  # معادن
    "4013",  # جرير
    "7010",  # STC
    "1010",  # الرياض
    "2350",  # كيمو
    "4160",  # تميم
    "2010",  # سابك
    "1120",  # الراجحي
    "1180",  # الجزيرة
]

DEFAULT_HALAL_US = [
    "MSFT",  # مايكروسوفت
    "AAPL",  # آبل
    "GOOG",  # جوجل
    "AMZN",  # أمازون
    "NVDA",  # انفيديا
    "TSM",   # TSMC
    "INTC",  # انتل
    "CSCO",  # سيسكو
]

def load_halal_stocks():
    """تحميل قائمة الأسهم الحلال المحفوظة"""
    if os.path.exists(HALAL_FILE):
        with open(HALAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"✅ تم تحميل {len(data['sa']) + len(data['us'])} سهم حلال")
            return data
    return {"sa": DEFAULT_HALAL_SA, "us": DEFAULT_HALAL_US, "updated": str(datetime.now())}

def save_halal_stocks(stocks):
    """حفظ قائمة الأسهم الحلال"""
    stocks["updated"] = str(datetime.now())
    with open(HALAL_FILE, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"💾 تم حفظ قائمة الأسهم الحلال")

def check_alrajhi_update():
    """فحص تحديثات قائمة الراجحي"""
    print("🔍 جاري فحص موقع الراجحي للتحديثات...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(
            "https://www.alrajhibank.com.sa/ar/alrajhi-capital/pages/sharia-compliant-stocks.aspx",
            headers=headers, timeout=10
        )
        if response.status_code == 200:
            print("✅ تم الاتصال بموقع الراجحي")
            return True
    except Exception as e:
        print(f"⚠️ لم يتم الاتصال بالراجحي: {e}")
    return False

def is_halal(ticker, market="SA"):
    """فحص هل السهم حلال"""
    stocks = load_halal_stocks()
    if market == "SA":
        return ticker in stocks["sa"]
    return ticker.upper() in stocks["us"]

def get_all_halal():
    """الحصول على كل الأسهم الحلال"""
    stocks = load_halal_stocks()
    return {"sa": stocks["sa"], "us": stocks["us"]}

if __name__ == "__main__":
    print("🕌 فاحص قائمة الراجحي")
    check_alrajhi_update()
    stocks = get_all_halal()
    print(f"📊 السعودي: {len(stocks['sa'])} سهم")
    print(f"📊 الأمريكي: {len(stocks['us'])} سهم")
