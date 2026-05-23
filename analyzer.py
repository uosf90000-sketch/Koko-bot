# ==========================================
# analyzer.py - محلل الأسهم بالذكاء الاصطناعي
# ==========================================

import requests
import json
import yfinance as yf
from config import CLAUDE_API_KEY

def get_stock_price(ticker, market="US"):
    """الحصول على سعر السهم الحالي"""
    try:
        if market == "SA":
            ticker = ticker + ".SR"
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            prev  = hist['Close'].iloc[-2] if len(hist) > 1 else price
            change = ((price - prev) / prev) * 100
            return {"price": round(price, 2), "change": round(change, 2), "success": True}
    except Exception as e:
        print(f"⚠️ خطأ في جلب سعر {ticker}: {e}")
    return {"price": 0, "change": 0, "success": False}

def get_rsi(ticker, market="US"):
    """حساب مؤشر RSI"""
    try:
        if market == "SA":
            ticker = ticker + ".SR"
        stock = yf.Ticker(ticker)
        hist = stock.history(period="30d")['Close']
        delta = hist.diff()
        gain  = delta.where(delta > 0, 0).rolling(14).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs    = gain / loss
        rsi   = 100 - (100 / (1 + rs))
        return round(rsi.iloc[-1], 2)
    except:
        return 50

def analyze_with_claude(ticker, name, price, change, rsi, market):
    """تحليل السهم بـ Claude AI"""
    try:
        currency = "ر.س" if market == "SA" else "$"
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "system": """أنت محلل مالي متخصص في الأسهم الحلال. أجب بالعربية فقط.
                قرر: شراء أو احتفظ أو بيع مع سبب موجز جداً (جملتين فقط).
                الإجابة بصيغة JSON فقط:
                {"signal": "شراء/احتفظ/بيع", "reason": "السبب", "confidence": 0-100}""",
                "messages": [{
                    "role": "user",
                    "content": f"سهم: {name} ({ticker})\nالسعر: {price} {currency}\nالتغير: {change}%\nRSI: {rsi}\nالسوق: {'سعودي' if market=='SA' else 'أمريكي'}"
                }]
            },
            timeout=30
        )
        data = response.json()
        text = data['content'][0]['text']
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"⚠️ خطأ في تحليل {ticker}: {e}")
        if rsi < 30:
            return {"signal": "شراء", "reason": "RSI في منطقة تشبع بيع", "confidence": 65}
        elif rsi > 70:
            return {"signal": "بيع", "reason": "RSI في منطقة تشبع شراء", "confidence": 65}
        return {"signal": "احتفظ", "reason": "السوق في توازن", "confidence": 50}

def analyze_stock(ticker, name, market="SA"):
    """تحليل شامل للسهم"""
    print(f"🔍 تحليل {name} ({ticker})...")
    price_data = get_stock_price(ticker, market)
    rsi = get_rsi(ticker, market)
    ai_analysis = analyze_with_claude(
        ticker, name,
        price_data['price'], price_data['change'],
        rsi, market
    )
    return {
        "ticker": ticker,
        "name": name,
        "market": market,
        "price": price_data['price'],
        "change": price_data['change'],
        "rsi": rsi,
        "signal": ai_analysis['signal'],
        "reason": ai_analysis['reason'],
        "confidence": ai_analysis['confidence']
    }

if __name__ == "__main__":
    result = analyze_stock("MSFT", "مايكروسوفت", "US")
    print(f"\n📊 النتيجة: {result['signal']} ({result['confidence']}%)")
    print(f"💡 السبب: {result['reason']}")
