import requests, time, hmac, hashlib, os, psycopg2
import pandas as pd
from datetime import datetime

class BinanceClient:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.db_url = os.getenv("DATABASE_URL")
        self.base_url = 'https://testnet.binancefuture.com'
        
        if self.db_url:
            if self.db_url.startswith("postgres://"):
                self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
            self._init_db()

    def _init_db(self):
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS trades (id SERIAL PRIMARY KEY, fecha TIMESTAMP, lado TEXT, entrada FLOAT, salida FLOAT, pnl FLOAT)")
            conn.commit(); cur.close(); conn.close()
        except: pass

    def get_indicators(self, symbol="BTCUSDT"):
        """Usa Bybit como fuente principal de velas para evitar bloqueos en Railway."""
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=15&limit=100"
        try:
            res = requests.get(url, timeout=5).json()
            data = res['result']['list']
            df = pd.DataFrame(data)
            # Bybit v5: [0]timestamp, [1]open, [2]high, [3]low, [4]close...
            closes = df[4].astype(float).iloc[::-1] # Invertimos para que el más reciente sea el último
            
            ema = closes.ewm(span=20, adjust=False).mean().iloc[-1]
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            return round(rsi, 2), round(ema, 2), closes.iloc[-1]
        except:
            return 0.0, 0.0, self.get_price(symbol)

    def get_price(self, symbol="BTCUSDT"):
        """Respaldo triple de precio: Bybit -> Coinbase -> CryptoCompare."""
        urls = [
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}",
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            "https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USDT"
        ]
        for url in urls:
            try:
                res = requests.get(url, timeout=2).json()
                if 'result' in res: return float(res['result']['list'][0]['lastPrice'])
                if 'data' in res: return float(res['data']['amount'])
                if 'USDT' in res: return float(res['USDT'])
            except: continue
        return 0.0

    def get_account_status(self):
        res = self._request('GET', '/fapi/v2/account')
        if isinstance(res, dict) and 'totalWalletBalance' in res:
            return {"wallet": float(res['totalWalletBalance']), "unrealized_pnl": float(res['totalUnrealizedProfit']), "equity": float(res['totalMarginBalance'])}
        return {"wallet": 0.0, "unrealized_pnl": 0.0, "equity": 0.0}

    def _request(self, method, endpoint, params={}):
        params['timestamp'] = int(time.time() * 1000)
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(self.secret_key.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        url = f"{self.base_url}{endpoint}?{query}&signature={signature}"
        headers = {'X-MBX-APIKEY': self.api_key}
        try:
            if method == 'POST': return requests.post(url, headers=headers, timeout=10).json()
            return requests.get(url, headers=headers, timeout=10).json()
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
        if not self.db_url: return
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("INSERT INTO trades (fecha, lado, entrada, salida, pnl) VALUES (%s, %s, %s, %s, %s)", (datetime.now(), side, entry, exit, round(pnl, 4)))
            conn.commit(); cur.close(); conn.close()
        except: pass

    def obtener_historial_db(self):
        if not self.db_url: return None
        try:
            conn = psycopg2.connect(self.db_url)
            df = pd.read_sql("SELECT fecha, lado, entrada, salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10", conn)
            conn.close()
            return df
        except: return None
