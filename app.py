import streamlit as st
import time, pandas as pd, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Demo Trading", layout="wide")
client = BinanceClient()

st.title("📈 Terminal de Trading (Demo)")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("Mi Cuenta")
    # Saldo en tiempo real
    saldo = client.get_balance()
    st.metric("Saldo Disponible", f"{saldo:,.2f} USDT")

    st.header("Parámetros de Orden")
    precio_actual = client.get_price("BTCUSDT")
    
    cantidad = st.number_input("CANTIDAD BTC", value=0.002, step=0.001, format="%.3f")
    
    # Visualización instantánea del precio en USDT
    valor_usdt = cantidad * precio_actual
    st.info(f"Valor aproximado: **{valor_usdt:,.2f} USDT**")
    
    tp_precio = st.number_input("Take Profit (USDT)", value=0.0, step=10.0)
    sl_precio = st.number_input("Stop Loss (USDT)", value=0.0, step=10.0)
    
    st.metric("Precio Bitcoin", f"{precio_actual:,.2f} USDT")

# --- GRÁFICO ---
components.html("""<div style="height:400px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart"});</script><div id="tv_chart"></div></div>""", height=400)

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")
if posicion and precio_actual > 0:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    pnl = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
    
    st.warning(f"**POSICIÓN ACTIVA: {side}** | Entrada: {entry:,.2f} | PNL: {'🟢' if pnl >= 0 else '🔴'} {pnl:,.2f} USDT")
    
    # Vigilancia TP/SL
    if (side=="LONG" and (0 < tp_precio <= precio_actual or 0 < sl_precio >= precio_actual)) or \
       (side=="SHORT" and (0 < tp_precio >= precio_actual or 0 < sl_precio <= precio_actual)):
        client.place_order("BTCUSDT", "SELL" if side=="LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl)
        st.rerun()
else:
    st.info("Buscando señal...")

# --- BOTONES DE ACCIÓN ---
col1, col2, col3 = st.columns(3)
if col1.button("🟢 ABRIR LONG"):
    client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
if col2.button("🔴 ABRIR SHORT"):
    client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()
if col3.button("⛔ CERRAR Y REGISTRAR"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side=="LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl); st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial de Trades")
if os.path.exists("historial_trades.csv"):
    st.table(pd.read_csv("historial_trades.csv").tail(10))

time.sleep(2); st.rerun()
