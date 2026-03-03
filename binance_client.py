import requests, time, hmac, hashlib, csv, os
from datetime import datetime

class BinanceClient:
    def __init__(self):
        # Railway lee estas variables desde su panel de 'Variables'
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.base_url = 'https://testnet.binancefuture.com' # URL oficial de Testnet

    def get_price(self, symbol="BTCUSDT"):
        """Triple respaldo: Binance Real -> Bybit -> CoinGecko."""
        urls = [
            f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}",
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}",
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        ]
        for url in urls:
            try:
                res = requests.get(url, timeout=2).json()
                if 'price' in res: return float(res['price'])
                if 'result' in res: return float(res['result']['list'][0]['lastPrice'])
                if 'bitcoin' in res: return float(res['bitcoin']['usd'])
            except: continue
        return 0.0

    def _send_request(self, method, endpoint, params):
        if not self.api_key or not self.secret_key:
            return {"error": "Llaves no configuradas en Railway"}
        
        params['timestamp'] = int(time.time() * 1000)
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(self.secret_key.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {'X-MBX-APIKEY': self.api_key}
        url = f"{self.base_url}{endpoint}?{query}&signature={signature}"
        
        try:
            if method == 'POST': return requests.post(url, headers=headers, timeout=5).json()
            return requests.get(url, headers=headers, timeout=5).json()
        except Exception as e:
            return {"error": str(e)}

    def place_order(self, symbol, side, quantity):
        return self._send_request('POST', '/fapi/v1/order', {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity})

    def get_open_positions(self, symbol="BTCUSDT"):
        data = self._send_request('GET', '/fapi/v2/account', {})
        if isinstance(data, dict) and 'positions' in data:
            for pos in data['positions']:
                if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0:
                    return pos
        return None

    def registrar_trade(self, side, entry, exit, pnl):
        archivo = "historial_trades.csv"
        existe = os.path.exists(archivo)
        with open(archivo, "a", newline='') as f:
            writer = csv.writer(f)
            if not existe or os.stat(archivo).st_size == 0:
                writer.writerow(["Fecha", "Side", "Entrada", "Salida", "PNL (USDT)"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), side, entry, exit, round(pnl, 2)])
