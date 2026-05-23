# ==========================================
# trader.py - منفذ الصفقات عبر IBKR
# ==========================================

import requests
import json
import time
from datetime import datetime
from config import *

BASE_URL = "https://api.ibkr.com/v1/api"
SESSION   = requests.Session()
TRADES_LOG = "trades.json"

def login():
    """تسجيل الدخول لـ IBKR"""
    try:
        response = SESSION.post(f"{BASE_URL}/iserver/auth/ssodh/init", json={
            "publish": True, "compete": True
        }, verify=False, timeout=30)
        if response.status_code == 200:
            print("✅ تم تسجيل الدخول لـ IBKR")
            return True
    except Exception as e:
        print(f"⚠️ خطأ في تسجيل الدخول: {e}")
    return False

def get_account_balance():
    """الحصول على الرصيد الحالي"""
    try:
        response = SESSION.get(f"{BASE_URL}/portfolio/accounts", verify=False, timeout=30)
        if response.status_code == 200:
            accounts = response.json()
            if accounts:
                account_id = accounts[0]['id']
                balance_resp = SESSION.get(
                    f"{BASE_URL}/portfolio/{account_id}/summary",
                    verify=False, timeout=30
                )
                if balance_resp.status_code == 200:
                    data = balance_resp.json()
                    return float(data.get('cashbalance', {}).get('amount', 0))
    except Exception as e:
        print(f"⚠️ خطأ في جلب الرصيد: {e}")
    return 0

def search_contract(ticker, market="US"):
    """البحث عن عقد السهم"""
    try:
        exchange = "SMART" if market == "US" else "TADAWUL"
        response = SESSION.get(
            f"{BASE_URL}/trsrv/stocks?symbols={ticker}",
            verify=False, timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            if ticker in data and data[ticker]:
                return data[ticker][0]['contracts'][0]['conid']
    except Exception as e:
        print(f"⚠️ خطأ في البحث عن {ticker}: {e}")
    return None

def place_order(ticker, name, action, quantity, price, market="US"):
    """تنفيذ أمر شراء أو بيع"""
    print(f"⚡ {'شراء' if action=='BUY' else 'بيع'} {quantity} سهم من {name}...")
    
    # في وضع التجريبي نسجل الصفقة فقط
    trade = {
        "time": str(datetime.now()),
        "ticker": ticker,
        "name": name,
        "action": action,
        "quantity": quantity,
        "price": price,
        "market": market,
        "total": round(quantity * price, 2),
        "status": "simulated"
    }
    
    if IBKR_ACCOUNT == "paper":
        print(f"📝 [تجريبي] تم تسجيل صفقة {'شراء' if action=='BUY' else 'بيع'} {name}")
        save_trade(trade)
        return {"success": True, "simulated": True, "trade": trade}
    
    # للحساب الحقيقي
    try:
        conid = search_contract(ticker, market)
        if not conid:
            return {"success": False, "error": "لم يتم العثور على السهم"}
        
        response = SESSION.post(f"{BASE_URL}/iserver/account/{IBKR_ACCOUNT}/orders", json={
            "orders": [{
                "conid": conid,
                "orderType": "MKT",
                "side": action,
                "quantity": quantity,
                "tif": "DAY"
            }]
        }, verify=False, timeout=30)
        
        if response.status_code in [200, 201]:
            trade["status"] = "executed"
            save_trade(trade)
            print(f"✅ تم تنفيذ {'شراء' if action=='BUY' else 'بيع'} {name} بنجاح!")
            return {"success": True, "trade": trade}
    except Exception as e:
        print(f"⚠️ خطأ في تنفيذ الأمر: {e}")
    
    return {"success": False}

def save_trade(trade):
    """حفظ الصفقة في السجل"""
    trades = load_trades()
    trades.append(trade)
    with open(TRADES_LOG, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)

def load_trades():
    """تحميل سجل الصفقات"""
    try:
        if os.path.exists(TRADES_LOG):
            with open(TRADES_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return []

def get_today_trades():
    """صفقات اليوم فقط"""
    today = datetime.now().strftime("%Y-%m-%d")
    return [t for t in load_trades() if t['time'].startswith(today)]

def calculate_pnl():
    """حساب الربح والخسارة"""
    trades = get_today_trades()
    total_bought = sum(t['total'] for t in trades if t['action'] == 'BUY')
    total_sold   = sum(t['total'] for t in trades if t['action'] == 'SELL')
    pnl = total_sold - total_bought
    return {"bought": total_bought, "sold": total_sold, "pnl": round(pnl, 2)}

import os
