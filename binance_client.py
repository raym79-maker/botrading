import requests, time, hmac, hashlib, os, psycopg2
import pandas as pd
from datetime import datetime

class BinanceClient:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.db_url = os.getenv("DATABASE_URL")
        self.base_url = 'https://testnet.binancefuture.com'
        
        # Variables Telegram
        self.tg_token = os.getenv("TELEGRAM_TOKEN")
        self.tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if self.db_url:
            # Corrección crítica de la URL de Postgres para Railway
            if self.db_url.startswith("postgres://"):
                self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
            self._init_db()

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """Guarda el trade usando la URL de base de datos corregida."""
        if not self.db_url: return False
        try:
            # Cambiado os.getenv por self.db_url que ya está corregida
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            query = """
                INSERT INTO trades (fecha, simbolo, lado, entrada, salida, pnl)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            valores = (datetime.now(), "BTCUSDT", side, entry_p, exit_p, pnl)
            
            cur.execute(query, valores)
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error al guardar en DB: {e}")
            return False

    def obtener_historial_db(self):
        """Recupera los trades para el Dashboard."""
        if not self.db_url: return None
        try:
            conn = psycopg2.connect(self.db_url)
            # Aseguramos que el SELECT coincida con las columnas del INSERT
            df = pd.read_sql("SELECT fecha, lado, entrada, salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10", conn)
            conn.close()
            return df
        except: return None

    # ... (Resto de funciones: enviar_telegram, get_indicators, etc., permanecen igual)
    def enviar_telegram(self, mensaje):
        if self.tg_token and self.tg_chat_id:
            url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
            try: requests.post(url, data={"chat_id": self.tg_chat_id, "text": mensaje, "parse_mode": "Markdown"}, timeout=5)
            except: pass

    def get_indicators(self, symbol="BTCUSDT"):
        try:
            res = requests.get("https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=15", timeout=4).json()
            data = res['result']['XXBTZUSD']
            df = pd.DataFrame(data)
            closes = df[4].astype(float)
            ema = closes.ewm(span=20, adjust=False).mean().iloc[-1]
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            return round(rsi, 2), round(ema, 2), closes.iloc[-1]
        except: return 0.0, 0.0, self.get_price(symbol)

    def get_price(self, symbol="BTCUSDT"):
        try:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=2).json()
            return float(r['price'])
        except: return 0.0

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
        try: return requests.request(method, url, headers={'X-MBX-APIKEY': self.api_key}, timeout=10).json()
        except: return {"error": "Error"}

    def place_order(self, symbol, side, quantity):
        return self._request('POST', '/fapi/v1/order', {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity})

    def get_open_positions(self, symbol="BTCUSDT"):
        data = self._request('GET', '/fapi/v2/account')
        if isinstance(data, dict) and 'positions' in data:
            for pos in data['positions']:
                if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0: return pos
        return None

    def _init_db(self):
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS trades (id SERIAL PRIMARY KEY, fecha TIMESTAMP, simbolo TEXT, lado TEXT, entrada FLOAT, salida FLOAT, pnl FLOAT)")
            conn.commit(); cur.close(); conn.close()
        except: pass
