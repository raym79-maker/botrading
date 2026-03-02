import requests, time, hmac, hashlib, csv, os
from datetime import datetime

class BinanceClient:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.base_url = 'https://demo-fapi.binance.com'

    def _get_signature(self, params):
        return hmac.new(self.secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

    def _get_timestamp(self):
        try:
            response = requests.get(f"{self.base_url}/fapi/v1/time", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'serverTime' in data:
                    return int(data['serverTime'])
            return int(time.time() * 1000)
        except Exception:
            return int(time.time() * 1000)

    def get_price(self, symbol="BTCUSDT"):
        try:
            return float(requests.get(f"{self.base_url}/fapi/v1/ticker/price?symbol={symbol}").json()['price'])
        except:
            return 0.0

    def place_order(self, symbol, side, quantity):
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity, "timestamp": self._get_timestamp()}
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        sig = self._get_signature(query_string)
        return requests.post(f"{self.base_url}/fapi/v1/order?{query_string}&signature={sig}", headers={'X-MBX-APIKEY': self.api_key}).json()

    def close_position(self, symbol, side, quantity):
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity, "reduceOnly": "true", "timestamp": self._get_timestamp()}
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        sig = self._get_signature(query_string)
        return requests.post(f"{self.base_url}/fapi/v1/order?{query_string}&signature={sig}", headers={'X-MBX-APIKEY': self.api_key}).json()

    def set_leverage(self, symbol, leverage):
        params = {"symbol": symbol, "leverage": leverage, "timestamp": self._get_timestamp()}
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        sig = self._get_signature(query_string)
        return requests.post(f"{self.base_url}/fapi/v1/leverage?{query_string}&signature={sig}", headers={'X-MBX-APIKEY': self.api_key}).json()

    def get_open_positions(self, symbol="BTCUSDT"):
        params = {"timestamp": self._get_timestamp()}
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        sig = self._get_signature(query_string)
        data = requests.get(f"{self.base_url}/fapi/v2/account?{query_string}&signature={sig}", headers={'X-MBX-APIKEY': self.api_key}).json()
        for pos in data.get('positions', []):
            if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0: return pos
        return None

    def registrar_trade(self, side, entry, exit, pnl):
        with open("historial_trades.csv", "a", newline='') as f:
            writer = csv.writer(f)
            if f.tell() == 0: writer.writerow(["Fecha", "Side", "Entrada", "Salida", "PNL (USDT)"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), side, entry, exit, round(pnl, 2)])
