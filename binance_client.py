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
        """Inicializa la conexión, el proxy y el motor de base de datos."""
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.bot_token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # Modo Testnet para cuenta Demo
        self.is_testnet = os.getenv("IS_TESTNET", "False").lower() == "true"
        
        # Configuración de Base de Datos
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        try:
            self.engine = create_engine(db_url)
        except Exception as e:
            print(f"Error motor SQL: {e}")

        # Configuración de Proxy (Vital en Railway/EE.UU. para evitar bloqueos)
        proxy_url = os.getenv("PROXY_URL") 
        self.proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

        # Inicialización del Cliente oficial
        try:
            if not self.api_key or not self.api_secret:
                self.client = None
                print("❌ Faltan credenciales API.")
            else:
                self.client = Client(
                    self.api_key, 
                    self.api_secret, 
                    testnet=self.is_testnet,
                    requests_params={'proxies': self.proxies, 'timeout': 20} if self.proxies else {'timeout': 20}
                )
                print(f"✅ Conexión establecida en modo: {'TESTNET' if self.is_testnet else 'REAL'}")
        except Exception as e:
            print(f"❌ Error de conexión Binance: {e}")
            self.client = None

    def get_indicators(self, symbol="BTCUSDT", interval="15m"):
        """Calcula RSI (14) y EMA (20) usando los datos más recientes."""
        if not self.client: return 0, 0, 0
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'cts', 'qv', 'nt', 'tbv', 'tqv', 'i'])
            df['c'] = df['c'].astype(float)
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            ema = ta.ema(df['c'], length=20).iloc[-1]
            return rsi, ema, df['c'].iloc[-1]
        except: return 0, 0, 0

    def get_account_status(self):
        """Consulta balance de margen y PNL no realizado."""
        if not self.client: return {"equity": 0.0, "unrealized_pnl": 0.0, "error": "API no configurada"}
        try:
            acc = self.client.futures_account()
            return {
                "equity": float(acc['totalMarginBalance']),
                "unrealized_pnl": float(acc['totalUnrealizedProfit']),
                "error": None
            }
        except Exception as e:
            return {"equity": 0.0, "unrealized_pnl": 0.0, "error": str(e)}

    def get_open_positions(self, symbol="BTCUSDT"):
        """Verifica si hay operaciones activas en futuros."""
        if not self.client: return None
        try:
            pos = self.client.futures_position_information(symbol=symbol)
            for p in pos:
                if float(p['positionAmt']) != 0: return p
            return None
        except: return None

    def place_order(self, symbol, side, amount):
        """Ejecuta una orden de mercado (MARKET)."""
        if not self.client: return None
        try:
            return self.client.futures_create_order(
                symbol=symbol, side=side, type="MARKET", quantity=str(amount)
            )
        except Exception as e:
            print(f"Error en orden: {e}")
            return None

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """Guarda la operación finalizada en la base de datos."""
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
        """Recupera los últimos 10 trades de PostgreSQL."""
        try:
            query = "SELECT fecha, lado, precio_entrada, precio_salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10"
            return pd.read_sql(query, self.engine)
        except: return None

    def enviar_telegram(self, mensaje):
        """Envía notificaciones al bot de Telegram."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            requests.post(url, data={"chat_id": self.chat_id, "text": mensaje, "parse_mode": "Markdown"})
        except: pass
