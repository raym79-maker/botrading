import streamlit as st
import time
import pandas as pd
import os
import streamlit.components.v1 as components
from binance_client import BinanceClient

# Configuración de página
st.set_page_config(page_title="Terminal Trading", layout="wide")

# CARGA DE CLAVES: En Railway es mejor usarlas desde la pestaña "Variables"
# Pero si las quieres dejar aquí para probar, asegúrate de que sean estas:
os.environ["API_KEY"] = "Z3EtogSRw4zn4UeO01WFjfvp4sbKM1k1iT9ydSPWFkbGuoYuGFHqI6qZXl2Twuav"
os.environ["SECRET_KEY"] = "lVPpfFljjpIBPpb4XAJe48CXpc8PXimDncCo24xHgH68LFpJVVM4ETEe1zWRsCju"

try:
    client = BinanceClient()
except Exception as e:
    st.error(f"Error al inicializar: {e}")
    st.stop()

st.title("📈 Terminal de Trading Local")

# --- GRÁFICO ---
components.html("""
<div style="height:400px;">
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "locale": "es", "container_id": "tv_chart"});
  </script>
  <div id="tv_chart"></div>
</div>
""", height=400)

# --- SIDEBAR (CONTROL) ---
st.sidebar.header("Control de Riesgo")
lev = st.sidebar.slider("Apalancamiento (x)", 1, 20, 20)
if st.sidebar.button("Aplicar Apalancamiento"):
    client.set_leverage("BTCUSDT", lev)
    st.sidebar.success("Aplicado")

cantidad = st.sidebar.number_input("Cantidad BTC", value=0.002, format="%.3f")
tp_precio = st.sidebar.number_input("Take Profit", value=0.0)
sl_precio = st.sidebar.number_input("Stop Loss", value=0.0)

precio_actual = client.get_price("BTCUSDT")
st.sidebar.metric("Precio Mercado", f"{precio_actual:,.2f} USDT")

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")
if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    pnl_flotante = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
    
    st.warning(f"OPERACIÓN {side} | Entrada: {entry:,.2f} | PNL: {pnl_flotante:,.2f} USDT")
    
    # Vigilancia automática
    if (side == "LONG" and (tp_precio > 0 and precio_actual >= tp_precio or sl_precio > 0 and precio_actual <= sl_precio)) or \
       (side == "SHORT" and (tp_precio > 0 and precio_actual <= tp_precio or sl_precio > 0 and precio_actual >= sl_precio)):
        lado = "SELL" if side == "LONG" else "BUY"
        client.close_position("BTCUSDT", lado, str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl_flotante)
        st.rerun()
else:
    st.success("Sin operaciones abiertas.")

# Botones
col1, col2, col3 = st.columns(3)
if col1.button("🟢 LONG"): client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
if col2.button("🔴 SHORT"): client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()
if col3.button("⛔ CERRAR"): 
    if posicion:
        lado = "SELL" if side == "LONG" else "BUY"
        client.close_position("BTCUSDT", lado, str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl_flotante)
        st.rerun()

# Historial
st.subheader("📋 Historial")
if os.path.exists("historial_trades.csv"):
    try:
        df = pd.read_csv("historial_trades.csv")
        st.table(df.tail(5))
    except:
        st.write("Historial vacío.")
else:
    st.write("Sin operaciones.")

time.sleep(1)
st.rerun()
