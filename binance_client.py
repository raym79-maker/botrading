import requests, time, hmac, hashlib, csv, os
from datetime import datetime

class BinanceClient:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        # URL para órdenes (Demo)
        self.base_url = 'https://demo-fapi.binance.com'
        # URLs para precio (Varios proveedores)
        self.sources = [
            'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',
            'https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT',
            'https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT'
        ]

    def get_price(self, symbol="BTCUSDT"):
        """Intenta obtener el precio de 3 fuentes distintas para evitar bloqueos de IP."""
        for url in self.sources:
            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    # Lógica para extraer el precio según el formato de cada API
                    if 'price' in data: 
                        return float(data['price'])
                    if 'result' in data: # Formato Bybit
                        return float(data['result']['list'][0]['lastPrice'])
            except:
                continue # Si falla esta fuente, intenta la siguiente
        return 0.0

    def _get_signature(self, params):
        return hmac.new(self.secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

    def _get_timestamp(self):
        return int(time.time() * 1000)

    def place_order(self, symbol, side, quantity):
        if not self.api_key or not self.secret_key:
            return {"error": "Faltan claves de API"}
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity, "timestamp": self._get_timestamp()}
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        sig = self._get_signature(query_string)
        headers = {'X-MBX-APIKEY': self.api_key}
        try:
            res = requests.post(f"{self.base_url}/fapi/v1/order?{query_string}&signature={sig}", headers=headers, timeout=5)
            return res.json()
        except Exception as e:
            return {"error": str(e)}

    def get_open_positions(self, symbol="BTCUSDT"):
        if not self.api_key or not self.secret_key: return None
        params = {"timestamp": self._get_timestamp()}
        query_string = f"timestamp={params['timestamp']}"
        sig = self._get_signature(query_string)
        headers = {'X-MBX-APIKEY': self.api_key}
        try:
            data = requests.get(f"{self.base_url}/fapi/v2/account?{query_string}&signature={sig}", headers=headers, timeout=5).json()
            if 'positions' in data:
                for pos in data['positions']:
                    if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0:
                        return pos
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
