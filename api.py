# ==========================================
# api.py - API للوحة التحكم
# ==========================================

import os
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

DATA_FILE = "bot_data.json"

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {
        "status": "running",
        "balance": 100,
        "trades": [],
        "last_analysis": [],
        "stats": {
            "total_trades": 0,
            "buy_signals": 0,
            "profit": 0
        },
        "updated": str(datetime.now())
    }

def save_data(data):
    data["updated"] = str(datetime.now())
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_trade(ticker, name, action, price, market):
    data = load_data()
    trade = {
        "ticker": ticker,
        "name": name,
        "action": action,
        "price": price,
        "market": market,
        "time": str(datetime.now()),
        "timeStr": datetime.now().strftime("%H:%M:%S")
    }
    data["trades"].insert(0, trade)
    data["trades"] = data["trades"][:50]
    data["stats"]["total_trades"] += 1
    if action == "شراء":
        data["stats"]["buy_signals"] += 1
    save_data(data)

def update_analysis(analyses):
    data = load_data()
    data["last_analysis"] = analyses
    save_data(data)

class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        data = load_data()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        pass

def start_api():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    print(f"✅ API شغّال على port {port}")
    server.serve_forever()

if __name__ == "__main__":
    start_api()
