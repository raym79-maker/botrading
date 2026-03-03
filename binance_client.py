import requests, time, hmac, hashlib, os, psycopg2
from datetime import datetime

class BinanceClient:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.db_url = os.getenv("DATABASE_URL")
        self.base_url = 'https://testnet.binancefuture.com'
        self._init_db()

    def _init_db(self):
        """Crea la tabla de trades en PostgreSQL si no existe."""
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                fecha TIMESTAMP,
                lado TEXT,
                entrada FLOAT,
                salida FLOAT,
                pnl FLOAT
            )
        """)
        conn.commit()
        cur.close()
        conn.close()

    def get_price(self, symbol="BTCUSDT"):
        sources = [
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}",
            f"https://api.coinbase.com/v2/prices/BTC-USD/spot"
        ]
        for url in sources:
            try:
                res = requests.get(url, timeout=2).json()
                if 'price' in res: return float(res['price'])
                if 'result' in res and 'list' in res['result']: return float(res['result']['list'][0]['lastPrice'])
                if 'data' in res: return float(res['data']['amount'])
            except: continue
        return 0.0

    def get_account_status(self):
        res = self._request('GET', '/fapi/v2/account')
        if isinstance(res, dict) and 'totalWalletBalance' in res:
            return {
                "wallet": float(res['totalWalletBalance']),
                "unrealized_pnl": float(res['totalUnrealizedProfit']),
                "equity": float(res['totalMarginBalance'])
            }
        return {"wallet": 0.0, "unrealized_pnl": 0.0, "equity": 0.0}

    def _request(self, method, endpoint, params={}):
        params['timestamp'] = int(time.time() * 1000)
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(self.secret_key.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {'X-MBX-APIKEY': self.api_key}
        url = f"{self.base_url}{endpoint}?{query}&signature={signature}"
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
        """Guarda el trade de forma permanente en PostgreSQL."""
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO trades (fecha, lado, entrada, salida, pnl) VALUES (%s, %s, %s, %s, %s)",
            (datetime.now(), side, entry, exit, round(pnl, 4))
        )
        conn.commit()
        cur.close()
        conn.close()

    def obtener_historial_db(self):
        """Recupera los últimos 10 trades de la base de datos."""
        conn = psycopg2.connect(self.db_url)
        import pandas as pd
        df = pd.read_sql("SELECT fecha, lado, entrada, salida, pnl FROM trades ORDER BY id DESC LIMIT 10", conn)
        conn.close()
        return df
