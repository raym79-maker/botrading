import requests, time, hmac, hashlib, csv, os
from datetime import datetime

class BinanceClient:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.base_url = 'https://testnet.binancefuture.com'

    def get_price(self, symbol="BTCUSDT"):
        """Intenta obtener el precio de 5 fuentes distintas para vencer el bloqueo de IP."""
        sources = [
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT",
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
            "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT"
        ]
        
        for url in sources:
            try:
                res = requests.get(url, timeout=1.5).json()
                # Lógica de extracción según la API que responda
                if 'price' in res: return float(res['price'])
                if 'result' in res:
                    if 'list' in res['result']: return float(res['result']['list'][0]['lastPrice'])
                    if 'XXBTZUSD' in res['result']: return float(res['result']['XXBTZUSD']['c'][0])
                if 'data' in res: return float(res['data']['amount'])
            except:
                continue
        return 0.0

    def _request(self, method, endpoint, params={}):
        if not self.api_key or not self.secret_key: return {"error": "Sin llaves"}
        params['timestamp'] = int(time.time() * 1000)
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(self.secret_key.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        url = f"{self.base_url}{endpoint}?{query}&signature={signature}"
        headers = {'X-MBX-APIKEY': self.api_key}
        try:
            if method == 'POST': return requests.post(url, headers=headers, timeout=5).json()
            return requests.get(url, headers=headers, timeout=5).json()
        except: return {"error": "Error de conexión"}

    def place_order(self, symbol, side, quantity):
        return self._request('POST', '/fapi/v1/order', {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity})

    def get_open_positions(self, symbol="BTCUSDT"):
        data = self._request('GET', '/fapi/v2/account')
        if isinstance(data, dict) and 'positions' in data:
            for pos in data['positions']:
                if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0: return pos
        return None

    def registrar_trade(self, side, entry, exit, pnl):
        archivo = "historial_trades.csv"
        existe = os.path.exists(archivo)
        with open(archivo, "a", newline='') as f:
            writer = csv.writer(f)
            if not existe or os.stat(archivo).st_size == 0:
                writer.writerow(["Fecha", "Side", "Entrada", "Salida", "PNL (USDT)"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), side, entry, exit, round(pnl, 2)])
