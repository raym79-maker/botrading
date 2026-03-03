import requests, time, hmac, hashlib, csv, os
from datetime import datetime

class BinanceClient:
    def __init__(self):
        # En Railway, configura estas variables en la pestaña 'Variables'
        self.api_key = os.getenv("API_KEY", "Z3EtogSRw4zn4UeO01WFjfvp4sbKM1k1iT9ydSPWFkbGuoYuGFHqI6qZXl2Twuav")
        self.secret_key = os.getenv("SECRET_KEY", "lVPpfFljjpIBPpb4XAJe48CXpc8PXimDncCo24xHgH68LFpJVVM4ETEe1zWRsCju")
        self.base_url = 'https://demo-fapi.binance.com'

    def get_price(self, symbol="BTCUSDT"):
        """Consulta el precio usando Binance Público o Bybit como respaldo."""
        urls = [
            f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}",
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        ]
        for url in urls:
            try:
                res = requests.get(url, timeout=2).json()
                if 'price' in res: return float(res['price'])
                if 'result' in res: return float(res['result']['list'][0]['lastPrice'])
            except: continue
        return 0.0

    def set_leverage(self, symbol, leverage):
        params = {"symbol": symbol, "leverage": leverage, "timestamp": int(time.time() * 1000)}
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        sig = hmac.new(self.secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return requests.post(f"{self.base_url}/fapi/v1/leverage?{query_string}&signature={sig}", headers={'X-MBX-APIKEY': self.api_key}).json()

    def place_order(self, symbol, side, quantity):
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity, "timestamp": int(time.time() * 1000)}
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        sig = hmac.new(self.secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return requests.post(f"{self.base_url}/fapi/v1/order?{query_string}&signature={sig}", headers={'X-MBX-APIKEY': self.api_key}).json()

    def get_open_positions(self, symbol="BTCUSDT"):
        ts = int(time.time() * 1000)
        sig = hmac.new(self.secret_key.encode('utf-8'), f"timestamp={ts}".encode('utf-8'), hashlib.sha256).hexdigest()
        try:
            data = requests.get(f"{self.base_url}/fapi/v2/account?timestamp={ts}&signature={sig}", headers={'X-MBX-APIKEY': self.api_key}, timeout=5).json()
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
