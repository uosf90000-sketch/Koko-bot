import os
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

DATA = {
    "status": "running",
    "balance": 100,
    "trades": [],
    "last_analysis": [
        {"ticker": "MSFT", "name": "مايكروسوفت", "price": 420.15, "change": 0.9, "signal": "شراء", "confidence": 85},
        {"ticker": "NVDA", "name": "انفيديا", "price": 875.20, "change": 3.1, "signal": "شراء", "confidence": 78},
        {"ticker": "AAPL", "name": "آبل", "price": 189.50, "change": -0.4, "signal": "احتفظ", "confidence": 65},
    ],
    "stats": {"total_trades": 0, "buy_signals": 3},
    "buy_signals_today": 3,
    "updated": str(datetime.now())
}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.end_headers()
        DATA["updated"] = str(datetime.now())
        self.wfile.write(json.dumps(DATA, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    print(f"✅ API شغّال على port {port}")
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()
