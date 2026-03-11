import requests, time, hmac, hashlib, os, psycopg2
import pandas as pd
from datetime import datetime

class BinanceClient:
    def __init__(self):
        """Inicializa credenciales, endpoints y base de datos."""
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.db_url = os.getenv("DATABASE_URL")
        self.base_url = 'https://testnet.binancefuture.com'
        
        # Variables para notificaciones de Telegram
        self.tg_token = os.getenv("TELEGRAM_TOKEN")
        self.tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if self.db_url:
            if self.db_url.startswith("postgres://"):
                self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
            self._init_db()

    def enviar_telegram(self, mensaje):
        """Envia alertas al canal de Telegram configurado."""
        if self.tg_token and self.tg_chat_id:
            url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
            try:
                data = {"chat_id": self.tg_chat_id, "text": mensaje, "parse_mode": "Markdown"}
                requests.post(url, data=data, timeout=5)
            except: pass

    def get_indicators(self, symbol="BTCUSDT"):
        """Calcula RSI y EMA usando la API de Kraken para estabilidad en Railway."""
        try:
            url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=15"
            res = requests.get(url, timeout=4).json()
            data = res['result']['XXBTZUSD']
            df = pd.DataFrame(data)
            closes = df[4].astype(float)
            
            ema = closes.ewm(span=20, adjust=False).mean().iloc[-1]
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            
            return round(rsi, 2), round(ema, 2), closes.iloc[-1]
        except:
            return 0.0, 0.0, self.get_price(symbol)

    def get_price(self, symbol="BTCUSDT"):
        """Obtiene precio actual desde Binance público en caso de fallo de Kraken."""
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            r = requests.get(url, timeout=2).json()
            return float(r['price'])
        except: return 0.0

    def set_leverage(self, symbol, leverage):
        """Configura el apalancamiento para el par especificado."""
        params = {"symbol": symbol, "leverage": int(leverage)}
        return self._request('POST', '/fapi/v1/leverage', params)

    def get_account_status(self):
        """Consulta balance de margen, balance de billetera y PNL en Binance Futuros."""
        res = self._request('GET', '/fapi/v2/account')
        if isinstance(res, dict) and 'totalWalletBalance' in res:
            return {
                "wallet": float(res['totalWalletBalance']),
                "unrealized_pnl": float(res['totalUnrealizedProfit']),
                "equity": float(res['totalMarginBalance'])
            }
        return {"wallet": 0.0, "unrealized_pnl": 0.0, "equity": 0.0}

    def _request(self, method, endpoint, params={}):
        """Firma peticiones privadas con HMAC-SHA256 para la API de Binance."""
        params['timestamp'] = int(time.time() * 1000)
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(self.secret_key.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
        url = f"{self.base_url}{endpoint}?{query}&signature={signature}"
        try:
            headers = {'X-MBX-APIKEY': self.api_key}
            return requests.request(method, url, headers=headers, timeout=10).json()
        except: return {"error": "Error de conexion"}

    def place_order(self, symbol, side, quantity):
        """Ejecuta ordenes de mercado (MARKET) en Binance Futuros."""
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity}
        return self._request('POST', '/fapi/v1/order', params)

    def get_open_positions(self, symbol="BTCUSDT"):
        """Busca y retorna informacion si existe una posicion abierta actualmente."""
        data = self._request('GET', '/fapi/v2/account')
        if isinstance(data, dict) and 'positions' in data:
            for p in data['positions']:
                if p.get('symbol') == symbol and float(p.get('positionAmt', 0)) != 0:
                    return p
        return None

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """Guarda los datos de la operacion finalizada en la tabla trades de PostgreSQL."""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            query = "INSERT INTO trades (fecha, simbolo, lado, entrada, salida, pnl) VALUES (%s, %s, %s, %s, %s, %s)"
            cur.execute(query, (datetime.now(), "BTCUSDT", side, entry_p, exit_p, pnl))
            conn.commit()
            cur.close() ; conn.close()
            return True
        except Exception as e:
            print(f"Error DB: {e}")
            return False

    def obtener_historial_db(self):
        """Recupera los ultimos 10 registros de operacion desde la base de datos."""
        if not self.db_url: return None
        try:
            conn = psycopg2.connect(self.db_url)
            query = "SELECT fecha, lado, entrada, salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10"
            df = pd.read_sql(query, conn)
            conn.close() ; return df
        except: return None

    def _init_db(self):
        """Crea la tabla necesaria en PostgreSQL si no existe al iniciar el bot."""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            schema = "id SERIAL PRIMARY KEY, fecha TIMESTAMP, simbolo TEXT, lado TEXT, entrada FLOAT, salida FLOAT, pnl FLOAT"
            cur.execute(f"CREATE TABLE IF NOT EXISTS trades ({schema})")
            conn.commit() ; cur.close() ; conn.close()
        except: pass
