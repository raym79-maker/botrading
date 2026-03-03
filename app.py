import streamlit as st
import time, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Trading Auto", layout="wide")
client = BinanceClient()

st.title("📈 Terminal de Trading (Auto RSI+EMA)")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("💰 Cuenta")
    info = client.get_account_status()
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    # MODO AUTOMÁTICO
    auto_mode = st.toggle("🤖 ACTIVAR ESTRATEGIA AUTO")
    st.header("⚙️ Configuración")
    cantidad = st.number_input("CANTIDAD BTC", value=0.002, format="%.3f")
    
    # Obtener indicadores
    rsi, ema, precio_actual = client.get_indicators()
    
    st.metric("RSI (14)", f"{rsi if rsi else 0}")
    st.metric("EMA 20", f"{ema if ema else 0}")
    st.metric("BTC Precio", f"{precio_actual:,.2f}")

# --- GRÁFICO ---
components.html("""<div style="height:400px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart"});</script><div id="tv_chart"></div></div>""", height=400)

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")

# SI HAY POSICIÓN: Gestión manual y cierre automático
if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    pnl = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
    st.warning(f"**POSICIÓN ACTIVA: {side}** | PNL: {'🟢' if pnl >= 0 else '🔴'} {pnl:,.4f} USDT")

# SI NO HAY POSICIÓN Y AUTO ESTÁ ON: Buscar entradas
elif auto_mode and precio_actual > 0:
    st.info("🤖 Bot analizando mercado...")
    # LÓGICA DE ENTRADA:
    # COMPRA: RSI < 35 (sobrevendido) y Precio cruza arriba de EMA 20
    if rsi < 35 and precio_actual > ema:
        client.place_order("BTCUSDT", "BUY", str(cantidad))
        st.success("🤖 Estrategia: Abriendo LONG (RSI Bajo + Cruce EMA)")
        time.sleep(1); st.rerun()
    # VENTA: RSI > 65 (sobrecomprado) y Precio cruza abajo de EMA 20
    elif rsi > 65 and precio_actual < ema:
        client.place_order("BTCUSDT", "SELL", str(cantidad))
        st.success("🤖 Estrategia: Abriendo SHORT (RSI Alto + Cruce EMA)")
        time.sleep(1); st.rerun()

# --- BOTONES MANUALES ---
st.divider()
c1, c2, c3 = st.columns(3)
if c1.button("🟢 MANUAL LONG"): client.place_order("BTCUSDT", "BUY", str(cantidad)) ; st.rerun()
if c2.button("🔴 MANUAL SHORT"): client.place_order("BTCUSDT", "SELL", str(cantidad)) ; st.rerun()
if c3.button("⛔ CERRAR Y REGISTRAR"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side=="LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl)
        st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial (DB)")
df = client.obtener_historial_db()
if df is not None: st.table(df)

time.sleep(2); st.rerun()
