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
        """
        Inicializa la conexión con Binance, la base de datos y el sistema de notificaciones.
        Gestiona automáticamente si se usa el servidor Real o el de Testnet (Demo).
        """
        # 1. Carga de Variables de Entorno desde Railway
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.bot_token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # 2. Configuración de Modo Prueba (Demo)
        # Si en Railway pones IS_TESTNET = True, se conectará a la red de prueba
        self.is_testnet = os.getenv("IS_TESTNET", "False").lower() == "true"
        
        # 3. Configuración de Base de Datos (PostgreSQL)
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        try:
            # Motor SQLAlchemy para lectura de datos rápida y estable
            self.engine = create_engine(db_url)
        except Exception as e:
            print(f"⚠️ Error al conectar motor SQLAlchemy: {e}")

        # 4. Configuración de Proxy (Vital para evitar el bloqueo de IP en Railway/EE.UU.)
        proxy_url = os.getenv("PROXY_URL") 
        self.proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

        # 5. Inicialización del Cliente oficial de Binance
        try:
            self.client = Client(
                self.api_key, 
                self.api_secret, 
                testnet=self.is_testnet,
                requests_params={'proxies': self.proxies, 'timeout': 20} if self.proxies else {'timeout': 20}
            )
            mode_str = "DEMO (Testnet)" if self.is_testnet else "REAL"
            print(f"✅ Conexión establecida con Binance en modo: {mode_str}")
        except Exception as e:
            print(f"❌ Fallo crítico al conectar con Binance API: {e}")
            self.client = None

    def get_indicators(self, symbol="BTCUSDT", interval="15m"):
        """
        Obtiene velas (klines) y calcula indicadores técnicos.
        Calcula: RSI (14) y EMA (20).
        """
        if not self.client: return 0, 0, 0
        try:
            # Pedimos las últimas 100 velas de 15 minutos
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=100)
            df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'cts', 'qv', 'nt', 'tbv', 'tqv', 'i'])
            df['c'] = df['c'].astype(float)
            
            # Usamos pandas_ta para cálculos profesionales
            rsi = ta.rsi(df['c'], length=14).iloc[-1]
            ema = ta.ema(df['c'], length=20).iloc[-1]
            precio_actual = df['c'].iloc[-1]
            
            return rsi, ema, precio_actual
        except Exception as e:
            print(f"⚠️ Error al obtener indicadores técnicos: {e}")
            return 0, 0, 0

    def get_account_status(self):
        """
        Consulta el Balance de Margen y el PNL no realizado de Futuros.
        Retorna un diccionario con los datos o el error específico.
        """
        if not self.client: 
            return {"equity": 0.0, "unrealized_pnl": 0.0, "error": "Cliente no inicializado"}
        try:
            # Binance Futuros requiere un endpoint específico (futures_account)
            acc = self.client.futures_account()
            return {
                "equity": float(acc['totalMarginBalance']),
                "unrealized_pnl": float(acc['totalUnrealizedProfit']),
                "error": None
            }
        except Exception as e:
            print(f"🚨 Error de API al consultar balance: {e}")
            return {"equity": 0.0, "unrealized_pnl": 0.0, "error": str(e)}

    def get_open_positions(self, symbol="BTCUSDT"):
        """
        Verifica si hay alguna posición abierta en el par especificado.
        """
        if not self.client: return None
        try:
            pos = self.client.futures_position_information(symbol=symbol)
            for p in pos:
                # Si la cantidad (positionAmt) es distinta a cero, hay trade activo
                if float(p['positionAmt']) != 0:
                    return p
            return None
        except Exception as e:
            print(f"⚠️ Error al consultar posiciones abiertas: {e}")
            return None

    def place_order(self, symbol, side, amount):
        """
        Ejecuta una orden de mercado (MARKET) en Binance Futuros.
        'side' debe ser 'BUY' o 'SELL'. 'amount' debe ser string.
        """
        if not self.client: return None
        try:
            order = self.client.futures_create_order(
                symbol=symbol, 
                side=side, 
                type="MARKET", 
                quantity=str(amount)
            )
            print(f"🚀 Orden {side} enviada con éxito: {amount} {symbol}")
            return order
        except Exception as e:
            print(f"🚨 Error de ejecución de orden en Binance: {e}")
            self.enviar_telegram(f"🚨 *FALLO EN OPERACIÓN:* `{e}`")
            return None

    def registrar_trade(self, side, entry_p, exit_p, pnl):
        """
        Guarda el registro de la operación finalizada en PostgreSQL.
        """
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
            print("💾 Trade registrado en la base de datos.")
            return True
        except Exception as e:
            print(f"❌ Error al registrar trade en PostgreSQL: {e}")
            return False

    def obtener_historial_db(self):
        """
        Recupera los últimos 10 registros de la base de datos para mostrarlos en el Dashboard.
        """
        try:
            query = "SELECT fecha, lado, precio_entrada, precio_salida, pnl FROM trades ORDER BY fecha DESC LIMIT 10"
            df = pd.read_sql(query, self.engine)
            return df
        except Exception as e:
            print(f"⚠️ Error al cargar historial de DB: {e}")
            return None

    def enviar_telegram(self, mensaje):
        """
        Envía notificaciones instantáneas al bot de Telegram.
        """
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": mensaje, "parse_mode": "Markdown"}
            requests.post(url, data=payload, timeout=5)
        except Exception as e:
            print(f"⚠️ Error de conexión con Telegram: {e}")
