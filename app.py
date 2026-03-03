import streamlit as st
import time, pandas as pd, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Demo Trading", layout="wide")
client = BinanceClient()

st.title("📈 Terminal de Trading (Demo)")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("Conexión")
    if not client.api_key: st.error("❌ API_KEY no configurada")
    else: st.success("✅ Conectado a Testnet")

    st.header("Parámetros")
    cantidad = st.number_input("Cantidad BTC", value=0.002, step=0.001, format="%.3f")
    tp_precio = st.number_input("Take Profit (USDT)", value=0.0, step=10.0)
    sl_precio = st.number_input("Stop Loss (USDT)", value=0.0, step=10.0)
    
    precio_actual = client.get_price("BTCUSDT")
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
        st.success("Objetivo alcanzado. Cerrando..."); time.sleep(1); st.rerun()
else:
    st.info("Buscando señal... No hay posiciones abiertas.")

# --- BOTONES ---
col1, col2, col3 = st.columns(3)
if col1.button("🟢 ABRIR LONG"):
    res = client.place_order("BTCUSDT", "BUY", str(cantidad))
    if 'orderId' not in res: st.error(f"Error: {res.get('msg', 'Desconocido')}")
    st.rerun()

if col2.button("🔴 ABRIR SHORT"):
    res = client.place_order("BTCUSDT", "SELL", str(cantidad))
    if 'orderId' not in res: st.error(f"Error: {res.get('msg', 'Desconocido')}")
    st.rerun()

if col3.button("⛔ CERRAR Y REGISTRAR"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side=="LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl)
        st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial de Trades")
if os.path.exists("historial_trades.csv"):
    df = pd.read_csv("historial_trades.csv")
    st.table(df.tail(10))

time.sleep(2); st.rerun()



