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
        """Inicializa credenciales, modo testnet, base de datos y proxies"""
        # 1. Carga de Variables de Entorno
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.bot_token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # 2. Configuración de Modo Prueba (Demo)
        # En Railway debes poner IS_TESTNET = True si usas cuenta Demo
        self.is_testnet = os.getenv("IS_TESTNET", "False").lower() == "true"
        
        # 3. Configuración de Base de Datos (PostgreSQL)
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        try:
            self.engine = create_engine(db_url)
        except Exception as e:
            print(f"⚠️ Error al conectar motor SQLAlchemy: {e}")

        # 4. Configuración de Proxy (Vital para Railway)
        proxy_url = os.getenv("PROXY_URL") 
        self.proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

        # 5. Inicialización del Cliente de Binance
        try:
            self.client = Client(
                self.api_key, 
                self.api_secret, 
                testnet=self.is_testnet,
                requests_params={'proxies': self.proxies, 'timeout': 20} if self.proxies else {'timeout': 20}
            )
            mode_str = "DEMO (Testnet)" if self.is_testnet else "REAL"
            print(f"✅ Cliente Binance vinculado con éxito en modo: {mode_str}")
        except Exception as e:
            print(f"❌ Fallo crítico al conectar con Binance: {e}")
            self.client = None

    def get_indicators(self, symbol="BTCUSDT", interval="15m"):
        """Calcula RSI y EMA 20 usando pandas_ta"""
        if not self.client: return 0, 0, 0
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'cts', 'qv', 'nt', 'tbv', 'tqv', 'i'])
            df['c'] = df['c'].astype(float)
            
            # Cálculo de indicadores técnicos
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            ema = ta.ema(df['c'], length=20).iloc[-1]
            precio_actual = df['c'].iloc[-1]
            
            return rsi, ema, precio_actual
        except Exception as e:
            print(f"⚠️ Error al obtener indicadores: {e}")
            return 0, 0, 0

    def get_account_status(self):
        """Obtiene el Balance y PNL no realizado de Futuros"""
        if not self.client: return {"equity": 0.0, "unrealized_pnl": 0.0}
        try:
            acc = self.client.futures_account()
            return {
                "equity": float(acc['totalMarginBalance']),
                "unrealized_pnl": float(acc['totalUnrealizedProfit'])
            }
        except Exception as e:
            print(f"⚠️ No se pudo obtener balance (Revisa API Keys): {e}")
            return {"equity": 0.0, "unrealized_pnl": 0.0}

    def get_open_positions(self, symbol="BTCUSDT"):
        """Busca si hay posiciones abiertas actualmente"""
        if not self.client: return None
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
        """Ejecuta una orden de mercado en Binance Futuros"""
        if not self.client: return None
        try:
            # Importante: Binance requiere la cantidad como string
            order = self.client.futures_create_order(
                symbol=symbol, 
                side=side, 
                type="MARKET", 
                quantity=str(amount)
            )
            print(f"🚀 Orden {side} ejecutada con éxito.")
            return order
        except Exception as e:
            print(f"🚨 Error de ejecución en Binance: {e}")
            self.enviar_telegram(f"🚨 *ERROR EN OPERACIÓN:* `{e}`")
            return None

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """Guarda la operación en la base de datos PostgreSQL"""
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
            print(f"❌ Error al registrar trade en DB: {e}")
            return False

    def obtener_historial_db(self):
        """Carga los últimos 10 trades del historial"""
        try:
            query = "SELECT fecha, lado, precio_entrada, precio_salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10"
            df = pd.read_sql(query, self.engine)
            return df
        except Exception as e:
            print(f"⚠️ Error al obtener historial: {e}")
            return None

    def enviar_telegram(self, mensaje):
        """Envía notificaciones al canal de Telegram configurado"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": mensaje, "parse_mode": "Markdown"}
            requests.post(url, data=payload, timeout=5)
        except Exception as e:
            print(f"⚠️ Error al enviar Telegram: {e}")
