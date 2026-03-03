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
        except Exception as e: print(f"Error DB: {e}")

    def get_price(self, symbol="BTCUSDT"):
        """Triple salto: Binance -> Bybit -> CryptoCompare (Infalible)."""
        urls = [
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}",
            "https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USDT"
        ]
        for url in urls:
            try:
                res = requests.get(url, timeout=2).json()
                if 'price' in res: return float(res['price'])
                if 'result' in res: return float(res['result']['list'][0]['lastPrice'])
                if 'USDT' in res: return float(res['USDT'])
            except: continue
        return 0.0

    def get_indicators(self, symbol="BTCUSDT"):
        """Obtiene velas para RSI/EMA. Si Binance bloquea, Bybit es el respaldo."""
        sources = [
            f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=100",
            f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval=15&limit=100"
        ]
        for url in sources:
            try:
                res = requests.get(url, timeout=3).json()
                data = res['result']['list'] if 'result' in res else res
                df = pd.DataFrame(data)
                # Extraemos cierres (columna 4 en ambos)
                closes = df[4].astype(float)
                if 'result' in res: closes = closes.iloc[::-1] # Bybit viene invertido
                
                ema = closes.ewm(span=20, adjust=False).mean().iloc[-1]
                delta = closes.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                return round(rsi, 2), round(ema, 2), closes.iloc[-1]
            except: continue
        return 0.0, 0.0, self.get_price(symbol)

    def set_leverage(self, symbol, leverage):
        return self._request('POST', '/fapi/v1/leverage', {"symbol": symbol, "leverage": int(leverage)})

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
        try:
            return requests.request(method, url, headers={'X-MBX-APIKEY': self.api_key}, timeout=10).json()
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
