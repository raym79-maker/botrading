import os, psycopg2, pandas as pd, requests
from binance.client import Client
from datetime import datetime
from sqlalchemy import create_engine
import pandas_ta as ta

class BinanceClient:
    def __init__(self):
        # 1. Credenciales desde Variables de Entorno (Railway)
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.client = Client(self.api_key, self.api_secret)
        self.bot_token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # 2. Motor SQL Reforzado (SQLAlchemy)
        # Esto soluciona el error de "UserWarning" y hace el historial más rápido
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        try:
            self.engine = create_engine(db_url)
        except Exception as e:
            print(f"⚠️ Error al crear motor SQL: {e}")

    def get_indicators(self, symbol="BTCUSDT", interval="15m"):
        """Calcula los sensores del Bot: RSI y EMA 20"""
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'cts', 'qv', 'nt', 'tbv', 'tqv', 'i'])
            df['c'] = df['c'].astype(float)
            
            # Usamos pandas_ta para máxima precisión
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            ema = ta.ema(df['c'], length=20).iloc[-1]
            precio = df['c'].iloc[-1]
            
            return rsi, ema, precio
        except Exception as e:
            print(f"❌ Error indicadores: {e}")
            return 0, 0, 0

    def get_account_status(self):
        """Monitorea el dinero en la cuenta de Futuros"""
        try:
            acc = self.client.futures_account()
            return {
                "equity": float(acc['totalMarginBalance']),
                "unrealized_pnl": float(acc['totalUnrealizedProfit'])
            }
        except Exception as e:
            print(f"❌ Error cuenta: {e}")
            return {"equity": 0.0, "unrealized_pnl": 0.0}

    def get_open_positions(self, symbol="BTCUSDT"):
        """Detecta si hay una operación corriendo ahora mismo"""
        try:
            pos = self.client.futures_position_information(symbol=symbol)
            for p in pos:
                if float(p['positionAmt']) != 0:
                    return p
            return None
        except Exception as e:
            print(f"❌ Error posiciones: {e}")
            return None

    def place_order(self, symbol, side, amount):
        """Envía la orden de compra o venta a Binance"""
        try:
            return self.client.futures_create_order(
                symbol=symbol, 
                side=side, 
                type="MARKET", 
                quantity=amount
            )
        except Exception as e:
            self.enviar_telegram(f"⚠️ *FALLO DE ORDEN*\nError: `{e}`")
            return None

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """Guarda los resultados en la base de datos de Railway"""
        try:
            # Conexión directa para escritura rápida
            conn = psycopg2.connect(os.getenv("DATABASE_URL"))
            cur = conn.cursor()
            
            query = """
                INSERT INTO trades (fecha, simbolo, lado, precio_entrada, precio_salida, pnl)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            valores = (datetime.now(), "BTCUSDT", side, entry_p, exit_p, pnl)
            
            cur.execute(query, valores)
            conn.commit()
            
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Error al registrar en DB: {e}")
            return False

    def obtener_historial_db(self):
        """Carga los últimos 10 trades para mostrar en la terminal"""
        try:
            query = "SELECT fecha, lado, precio_entrada, precio_salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10"
            # Usamos SQLAlchemy para evitar avisos de Pandas
            df = pd.read_sql(query, self.engine)
            return df
        except Exception as e:
            print(f"❌ Error al leer historial: {e}")
            return None

    def enviar_telegram(self, mensaje):
        """El mensajero que te avisa al celular"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": mensaje, "parse_mode": "Markdown"}
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            print(f"❌ Error Telegram: {e}")
