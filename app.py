import streamlit as st
import time, pandas as pd, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Trading", layout="wide")

try:
    client = BinanceClient()
except Exception as e:
    st.error(f"Error: {e}"); st.stop()

st.title("📈 Terminal de Trading")

# --- GRÁFICO ---
components.html("""<div style="height:400px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "style": "1", "locale": "es", "container_id": "tv_chart"});</script><div id="tv_chart"></div></div>""", height=400)

# --- PANEL LATERAL ---
st.sidebar.header("Control de Riesgo")
lev = st.sidebar.slider("Apalancamiento (x)", 1, 20, 20)
if st.sidebar.button("Aplicar Apalancamiento"):
    res = client.set_leverage("BTCUSDT", lev)
    st.sidebar.json(res)

cantidad = st.sidebar.number_input("Cantidad BTC", value=0.002, format="%.3f")
tp_precio = st.sidebar.number_input("Take Profit (USDT)", value=0.0, format="%.2f")
sl_precio = st.sidebar.number_input("Stop Loss (USDT)", value=0.0, format="%.2f")

precio_actual = client.get_price("BTCUSDT")
st.sidebar.metric("Precio Mercado", f"{precio_actual:,.2f} USDT")

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")
if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    pnl_flotante = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
    st.warning(f"**POSICIÓN {side}** | Entrada: {entry:,.2f} | PNL: {pnl_flotante:,.2f} USDT")

    # Cierre automático por TP/SL
    if (side == "LONG" and (tp_precio > 0 and precio_actual >= tp_precio or sl_precio > 0 and precio_actual <= sl_precio)) or \
       (side == "SHORT" and (tp_precio > 0 and precio_actual <= tp_precio or sl_precio > 0 and precio_actual >= sl_precio)):
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl_flotante)
        st.rerun()
else: st.info("Buscando señal...")

# --- BOTONES ---
col1, col2, col3 = st.columns(3)
if col1.button("🟢 LONG"): client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
if col2.button("🔴 SHORT"): client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()
if col3.button("⛔ CERRAR Y REGISTRAR"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl_flotante)
        st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial")
if os.path.exists("historial_trades.csv"):
    df = pd.read_csv("historial_trades.csv")
    st.table(df.tail(10))

time.sleep(2); st.rerun()
