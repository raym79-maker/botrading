import os
import psycopg2
import pandas as pd
import requests
from binance.client import Client
from datetime import datetime
from sqlalchemy import create_engine
import pandas_ta as ta

class BinanceClient:
    def __init__(self):
        # 1. Carga de Variables de Entorno
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.bot_token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.is_testnet = os.getenv("IS_TESTNET", "False").lower() == "true"
        
        # 2. Configuración de Base de Datos (PostgreSQL)
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        try:
            self.engine = create_engine(db_url)
        except Exception as e:
            print(f"⚠️ Error motor SQL: {e}")

        # 3. Configuración de Proxy (Crucial para saltar el bloqueo de Railway)
        proxy_url = os.getenv("PROXY_URL") 
        self.proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

        # 4. Inicialización del Cliente de Binance
        try:
            self.client = Client(
                self.api_key, 
                self.api_secret, 
                testnet=self.is_testnet,
                requests_params={'proxies': self.proxies, 'timeout': 20} if self.proxies else {'timeout': 20}
            )
            print(f"✅ Conectado a Binance {'TESTNET' (Demo) if self.is_testnet else 'REAL'}")
        except Exception as e:
            print(f"❌ Fallo crítico de conexión: {e}")
            self.client = None

    def get_indicators(self, symbol="BTCUSDT", interval="15m"):
        """Calcula RSI y EMA 20 con datos actuales"""
        if not self.client: return 0, 0, 0
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'cts', 'qv', 'nt', 'tbv', 'tqv', 'i'])
            df['c'] = df['c'].astype(float)
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            ema = ta.ema(df['c'], length=20).iloc[-1]
            return rsi, ema, df['c'].iloc[-1]
        except Exception as e:
            print(f"⚠️ Error indicadores: {e}")
            return 0, 0, 0

    def get_account_status(self):
        """Obtiene el Balance y PNL de Futuros"""
        if not self.client: return {"equity": 0.0, "unrealized_pnl": 0.0, "error": "Sin cliente"}
        try:
            acc = self.client.futures_account()
            return {
                "equity": float(acc['totalMarginBalance']),
                "unrealized_pnl": float(acc['totalUnrealizedProfit']),
                "error": None
            }
        except Exception as e:
            print(f"🚨 Error de balance: {e}")
            return {"equity": 0.0, "unrealized_pnl": 0.0, "error": str(e)}

    def get_open_positions(self, symbol="BTCUSDT"):
        """Busca si hay alguna posición activa"""
        if not self.client: return None
        try:
            pos = self.client.futures_position_information(symbol=symbol)
            for p in pos:
                if float(p['positionAmt']) != 0: return p
            return None
        except: return None

    def place_order(self, symbol, side, amount):
        """Ejecuta órdenes de mercado en Binance Futuros"""
        if not self.client: return None
        try:
            order = self.client.futures_create_order(
                symbol=symbol, side=side, type="MARKET", quantity=str(amount)
            )
            print(f"✅ Orden {side} ejecutada con éxito.")
            return order
        except Exception as e:
            print(f"🚨 Error en orden: {e}")
            return None

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """Guarda trades en PostgreSQL"""
        try:
            conn = psycopg2.connect(os.getenv("DATABASE_URL"))
            cur = conn.cursor()
            query = """INSERT INTO trades (fecha, simbolo, lado, precio_entrada, precio_salida, pnl) 
                       VALUES (%s, %s, %s, %s, %s, %s)"""
            cur.execute(query, (datetime.now(), "BTCUSDT", side, entry_p, exit_p, pnl))
            conn.commit()
            cur.close() ; conn.close()
            return True
        except: return False

    def obtener_historial_db(self):
        """Carga los trades usando SQLAlchemy"""
        try:
            query = "SELECT fecha, lado, precio_entrada, precio_salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10"
            return pd.read_sql(query, self.engine)
        except: return None

    def enviar_telegram(self, mensaje):
        """Notificaciones"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            requests.post(url, data={"chat_id": self.chat_id, "text": mensaje, "parse_mode": "Markdown"})
        except: pass
