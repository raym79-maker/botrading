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
        # 1. Carga de credenciales desde Railway
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.bot_token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # 2. Motor de Base de Datos (SQLAlchemy para estabilidad)
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        try:
            self.engine = create_engine(db_url)
        except Exception as e:
            print(f"⚠️ Error en motor SQL: {e}")

        # 3. Configuración de Proxy (Crucial para saltar el bloqueo de Railway)
        proxy_url = os.getenv("PROXY_URL") 
        self.proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

        # 4. Inicialización del Cliente con manejo de errores de ubicación
        try:
            self.client = Client(
                self.api_key, 
                self.api_secret, 
                requests_params={'proxies': self.proxies, 'timeout': 10} if self.proxies else {'timeout': 10}
            )
            print("✅ Cliente Binance vinculado con éxito.")
        except Exception as e:
            print(f"❌ Fallo crítico de conexión (Ubicación Restringida): {e}")
            self.client = None

    def get_indicators(self, symbol="BTCUSDT", interval="15m"):
        """Calcula RSI y EMA 20 con datos en tiempo real"""
        if not self.client: return 0, 0, 0
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'cts', 'qv', 'nt', 'tbv', 'tqv', 'i'])
            df['c'] = df['c'].astype(float)
            
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            ema = ta.ema(df['c'], length=20).iloc[-1]
            precio_actual = df['c'].iloc[-1]
            
            return rsi, ema, precio_actual
        except Exception as e:
            print(f"⚠️ Error en indicadores (IP bloqueada por Binance): {e}")
            return 0, 0, 0

    def get_account_status(self):
        """Monitorea el dinero disponible y el PNL"""
        if not self.client: return {"equity": 0.0, "unrealized_pnl": 0.0}
        try:
            acc = self.client.futures_account()
            return {
                "equity": float(acc['totalMarginBalance']),
                "unrealized_pnl": float(acc['totalUnrealizedProfit'])
            }
        except:
            return {"equity": 0.0, "unrealized_pnl": 0.0}

    def get_open_positions(self, symbol="BTCUSDT"):
        """Verifica si el bot ya tiene una operación abierta"""
        if not self.client: return None
        try:
            pos = self.client.futures_position_information(symbol=symbol)
            for p in pos:
                if float(p['positionAmt']) != 0:
                    return p
            return None
        except:
            return None

    def place_order(self, symbol, side, amount):
        """Envía la orden de compra o venta a Binance Futuros"""
        if not self.client: return None
        try:
            return self.client.futures_create_order(
                symbol=symbol, side=side, type="MARKET", quantity=amount
            )
        except Exception as e:
            self.enviar_telegram(f"🚨 *FALLO EN ORDEN*: {e}")
            return None

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """Guarda el resultado del trade en PostgreSQL"""
        try:
            conn = psycopg2.connect(os.getenv("DATABASE_URL"))
            cur = conn.cursor()
            query = """INSERT INTO trades (fecha, simbolo, lado, precio_entrada, precio_salida, pnl) 
                       VALUES (%s, %s, %s, %s, %s, %s)"""
            cur.execute(query, (datetime.now(), "BTCUSDT", side, entry_p, exit_p, pnl))
            conn.commit()
            cur.close() ; conn.close()
            return True
        except Exception as e:
            print(f"❌ Error DB: {e}")
            return False

    def obtener_historial_db(self):
        """Carga los trades pasados para la tabla visual"""
        try:
            query = "SELECT fecha, lado, precio_entrada, precio_salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10"
            return pd.read_sql(query, self.engine)
        except:
            return None

    def enviar_telegram(self, mensaje):
        """Avisos al celular"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            requests.post(url, data={"chat_id": self.chat_id, "text": mensaje, "parse_mode": "Markdown"})
        except:
            pass
