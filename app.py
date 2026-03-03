import streamlit as st
import time
import pandas as pd
import os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Trading", layout="wide")

try:
    client = BinanceClient()
except Exception as e:
    st.error(f"Error de inicialización: {e}")
    st.stop()

st.title("📈 Terminal de Trading Local")

# --- GRÁFICO INTEGRADO ---
components.html("""
<div class="tradingview-widget-container" style="height:400px; width:100%;">
  <div id="tradingview_chart" style="height:100%; width:100%;"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "locale": "es", "container_id": "tradingview_chart"});
  </script>
</div>
""", height=400)

# --- PANEL LATERAL ---
st.sidebar.header("Control")
cantidad = st.sidebar.number_input("Cantidad BTC", value=0.002, format="%.3f")

# PRECIO EN TIEMPO REAL
precio_actual = client.get_price("BTCUSDT")
st.sidebar.metric("Precio Mercado", f"{precio_actual:,.2f} USDT")

# --- BOTONES Y LÓGICA ---
posicion = client.get_open_positions("BTCUSDT")

col1, col2, col3 = st.columns(3)
if col1.button("🟢 LONG"):
    client.place_order("BTCUSDT", "BUY", str(cantidad))
    st.rerun()

if col2.button("🔴 SHORT"):
    client.place_order("BTCUSDT", "SELL", str(cantidad))
    st.rerun()

if col3.button("⛔ CERRAR"):
    if posicion:
        # Lógica de cierre y registro similar a la local
        st.success("Cerrando posición...")
        st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial")
if os.path.exists("historial_trades.csv"):
    df = pd.read_csv("historial_trades.csv")
    st.table(df.tail(5))

# REFRESCAR CADA 2 SEGUNDOS
time.sleep(2)
st.rerun()
