import streamlit as st
import time, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Trading Auto", layout="wide")
client = BinanceClient()

st.title("🤖 Terminal Trading (Auto RSI+EMA)")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("💰 Cuenta")
    info = client.get_account_status()
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    auto_mode = st.toggle("🚀 ACTIVAR ESTRATEGIA AUTO")
    st.header("⚙️ Configuración")
    cantidad = st.number_input("CANTIDAD BTC", value=0.002, format="%.3f")
    
    rsi, ema, precio_actual = client.get_indicators()
    st.metric("RSI (14)", f"{rsi if rsi > 0 else 'Cargando...'}")
    st.metric("EMA (20)", f"{ema if ema > 0 else 'Cargando...'}")
    st.metric("BTC Precio", f"{precio_actual:,.2f} USDT")

# --- GRÁFICO CON EMA Y RSI VISIBLES ---
components.html(f"""
<div style="height:450px;">
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart",
    "studies": ["RSI@tv-basicstudies", "Moving Average Exponential@tv-basicstudies"]
  }});
  </script>
  <div id="tv_chart"></div>
</div>
""", height=450)

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")
pnl = 0.0 # Inicializamos PNL para evitar el error 'NameError'

if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    if precio_actual > 0:
        pnl = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
        st.warning(f"**POSICIÓN ACTIVA: {side}** | PNL: {'🟢' if pnl >= 0 else '🔴'} {pnl:,.4f} USDT")
    else:
        st.info(f"**POSICIÓN ACTIVA: {side}** | Esperando precio real para calcular PNL...")

elif auto_mode and precio_actual > 0 and rsi > 0:
    st.info("🤖 Bot analizando mercado...")
    # LONG: RSI < 35 y precio por encima de EMA 20
    if rsi < 35 and precio_actual > ema:
        client.place_order("BTCUSDT", "BUY", str(cantidad))
        st.rerun()
    # SHORT: RSI > 65 y precio por debajo de EMA 20
    elif rsi > 65 and precio_actual < ema:
        client.place_order("BTCUSDT", "SELL", str(cantidad))
        st.rerun()

# --- BOTONES ---
st.divider()
c1, c2, c3 = st.columns(3)
if c1.button("🟢 FORZAR LONG"): client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
if c2.button("🔴 FORZAR SHORT"): client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()
if c3.button("⛔ CERRAR Y REGISTRAR"):
    if posicion:
        # Si el precio falló, calculamos un PNL estimado de 0 para evitar el error
        pnl_final = pnl if precio_actual > 0 else 0.0
        client.place_order("BTCUSDT", "SELL" if side=="LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl_final)
        st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial Permanente (DB)")
df = client.obtener_historial_db()
if df is not None: st.table(df)

time.sleep(2); st.rerun()
