import streamlit as st
import time, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Trading Pro", layout="wide")
client = BinanceClient()

st.title("📈 Terminal de Trading (Modo Persistente)")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("💰 Estado de Cuenta")
    info = client.get_account_status()
    st.metric(
        label="Patrimonio Total (Equity)", 
        value=f"{info['equity']:,.2f} USDT", 
        delta=f"{info['unrealized_pnl']:,.2f} USDT PNL"
    )
    st.write(f"**Saldo Billetera:** {info['wallet']:,.2f} USDT")
    
    st.divider()
    if not client.db_url: st.error("⚠️ Base de Datos NO vinculada.")
    else: st.success("✅ Base de Datos Conectada.")

    st.header("⚙️ Parámetros")
    cantidad = st.number_input("CANTIDAD BTC", value=0.002, format="%.3f")
    precio_actual = client.get_price("BTCUSDT")
    
    tp_precio = st.number_input("Take Profit (USDT)", value=0.0)
    sl_precio = st.number_input("Stop Loss (USDT)", value=0.0)
    st.metric("Precio Bitcoin", f"{precio_actual:,.2f} USDT")

# --- GRÁFICO ---
components.html("""<div style="height:400px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart"});</script><div id="tv_chart"></div></div>""", height=400)

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")
if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    if precio_actual > 0:
        pnl = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
        st.warning(f"**POSICIÓN ACTIVA: {side}** | Entrada: {entry:,.2f} | PNL: {'🟢' if pnl >= 0 else '🔴'} {pnl:,.4f} USDT")
        
        # Vigilancia automática TP/SL
        if (side=="LONG" and (0 < tp_precio <= precio_actual or 0 < sl_precio >= precio_actual)) or \
           (side=="SHORT" and (0 < tp_precio >= precio_actual or 0 < sl_precio <= precio_actual)):
            client.place_order("BTCUSDT", "SELL" if side=="LONG" else "BUY", str(tamano))
            client.registrar_trade(side, entry, precio_actual, pnl)
            st.rerun()
    else:
        st.info(f"**POSICIÓN ACTIVA: {side}** | Sincronizando precio real...")
else:
    st.info("Buscando señal... No hay posiciones abiertas.")

# --- BOTONES ---
col1, col2, col3 = st.columns(3)
if col1.button("🟢 ABRIR LONG"): client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
if col2.button("🔴 ABRIR SHORT"): client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()
if col3.button("⛔ CERRAR Y REGISTRAR"):
    if posicion and precio_actual > 0:
        pnl_final = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
        client.place_order("BTCUSDT", "SELL" if side=="LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl_final)
        st.rerun()

# --- HISTORIAL PERMANENTE (POSTGRESQL) ---
st.subheader("📋 Historial Permanente")
historial = client.obtener_historial_db()
if historial is not None and not historial.empty:
    st.table(historial)
else:
    st.write("Esperando el primer cierre de operación para registrar en la DB.")

time.sleep(2); st.rerun()
