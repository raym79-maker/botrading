import requests, time, hmac, hashlib, csv, os
from datetime import datetime

class BinanceClient:
    def __init__(self):
        # IMPORTANTE: En Railway, ve a 'Variables' y añade API_KEY y SECRET_KEY
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.base_url = 'https://demo-fapi.binance.com'

    def get_price(self, symbol="BTCUSDT"):
        """Intenta Binance; si falla, usa Bybit (evita el 0.00 en la nube)."""
        urls = [
            f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}",
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        ]
        for url in urls:
            try:
                res = requests.get(url, timeout=2).json()
                if 'price' in res: return float(res['price'])
                if 'result' in res: return float(res['result']['list'][0]['lastPrice'])
            except: continue
        return 0.0

    def _send_request(self, method, endpoint, params):
        if not self.api_key or not self.secret_key:
            return {"error": "Faltan claves en Variables de Railway"}
        
        params['timestamp'] = int(time.time() * 1000)
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(self.secret_key.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        url = f"{self.base_url}{endpoint}?{query}&signature={signature}"
        headers = {'X-MBX-APIKEY': self.api_key}
        
        if method == 'POST': return requests.post(url, headers=headers).json()
        return requests.get(url, headers=headers).json()

    def set_leverage(self, symbol, leverage):
        return self._send_request('POST', '/fapi/v1/leverage', {"symbol": symbol, "leverage": leverage})

    def place_order(self, symbol, side, quantity):
        return self._send_request('POST', '/fapi/v1/order', {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity})

    def get_open_positions(self, symbol="BTCUSDT"):
        try:
            data = self._send_request('GET', '/fapi/v2/account', {})
            for pos in data.get('positions', []):
                if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0: return pos
        except: pass
        return None

    def registrar_trade(self, side, entry, exit, pnl):
        archivo = "historial_trades.csv"
        existe = os.path.exists(archivo)
        with open(archivo, "a", newline='') as f:
            writer = csv.writer(f)
            if not existe or os.stat(archivo).st_size == 0:
                writer.writerow(["Fecha", "Side", "Entrada", "Salida", "PNL (USDT)"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), side, entry, exit, round(pnl, 2)])
