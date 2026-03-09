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
        """Inicializa credenciales, base de datos y cliente Binance"""
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.bot_token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # 1. Configuración de Base de Datos (Motor SQLAlchemy para evitar advertencias)
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        try:
            self.engine = create_engine(db_url)
        except Exception as e:
            print(f"⚠️ Error al configurar el motor SQL: {e}")

        # 2. Configuración de Proxy (Necesario si Binance bloquea la IP de Railway)
        proxy_url = os.getenv("PROXY_URL") 
        proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else {}

        # 3. Iniciar Cliente de Binance
        try:
            self.client = Client(
                self.api_key, 
                self.api_secret, 
                requests_params={'proxies': proxies} if proxy_url else {}
            )
            print("✅ Cliente Binance conectado satisfactoriamente")
        except Exception as e:
            print(f"❌ Fallo crítico de conexión con Binance: {e}")
            self.client = None

    def get_indicators(self, symbol="BTCUSDT", interval="15m"):
        """Obtiene datos de mercado y calcula RSI y EMA 20"""
        if not self.client:
            return 0, 0, 0
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'cts', 'qv', 'nt', 'tbv', 'tqv', 'i'])
            df['c'] = df['c'].astype(float)
            
            # Cálculo de indicadores técnicos usando pandas_ta
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            ema = ta.ema(df['c'], length=20).iloc[-1]
            precio_actual = df['c'].iloc[-1]
            
            return rsi, ema, precio_actual
        except Exception as e:
            print(f"⚠️ Error al obtener indicadores (Posible bloqueo de IP): {e}")
            return 0, 0, 0

    def get_account_status(self):
        """Métrica de Balance y PNL no realizado en Futuros"""
        if not self.client:
            return {"equity": 0.0, "unrealized_pnl": 0.0}
        try:
            acc = self.client.futures_account()
            return {
                "equity": float(acc['totalMarginBalance']),
                "unrealized_pnl": float(acc['totalUnrealizedProfit'])
            }
        except Exception as e:
            print(f"⚠️ Error al consultar balance: {e}")
            return {"equity": 0.0, "unrealized_pnl": 0.0}

    def get_open_positions(self, symbol="BTCUSDT"):
        """Busca si hay alguna operación activa en el par seleccionado"""
        if not self.client:
            return None
        try:
            pos = self.client.futures_position_information(symbol=symbol)
            for p in pos:
                if float(p['positionAmt']) != 0:
                    return p
            return None
        except Exception as e:
            print(f"⚠️ Error al consultar posiciones: {e}")
            return None

    def place_order(self, symbol, side, amount):
        """Ejecuta una orden de mercado (MARKET) en Futuros"""
        if not self.client:
            return None
        try:
            return self.client.futures_create_order(
                symbol=symbol, 
                side=side, 
                type="MARKET", 
                quantity=amount
            )
        except Exception as e:
            self.enviar_telegram(f"🚨 *ERROR BINANCE:* No se pudo ejecutar {side}.\n`{e}`")
            return None

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """Guarda el resultado del trade en la base de datos PostgreSQL"""
        try:
            conn = psycopg2.connect(os.getenv("DATABASE_URL"))
            cur = conn.cursor()
            query = """
                INSERT INTO trades (fecha, simbolo, lado, precio_entrada, precio_salida, pnl)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(query, (datetime.now(), "BTCUSDT", side, entry_p, exit_p, pnl))
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Error al registrar en PostgreSQL: {e}")
            return False

    def obtener_historial_db(self):
        """Recupera el historial de trades usando el motor SQLAlchemy"""
        try:
            query = "SELECT fecha, lado, precio_entrada, precio_salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10"
            df = pd.read_sql(query, self.engine)
            return df
        except Exception as e:
            print(f"⚠️ Error al leer historial: {e}")
            return None

    def enviar_telegram(self, mensaje):
        """Envía notificaciones instantáneas a Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": mensaje, "parse_mode": "Markdown"}
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            print(f"⚠️ Error al enviar Telegram: {e}")
