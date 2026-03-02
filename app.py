import streamlit as st
import time, pandas as pd
import streamlit.components.v1 as components
from binance_client import BinanceClient

@st.cache_resource
def get_client(): return BinanceClient()
client = get_client()

st.title("🤖 Terminal de Trading Pro")

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

# --- SIDEBAR (CONTROL) ---
st.sidebar.header("Control de Riesgo")
lev = st.sidebar.slider("Apalancamiento (x)", 1, 20, 20)
if st.sidebar.button("Aplicar Apalancamiento"):
    client.set_leverage("BTCUSDT", lev)
    st.sidebar.success("Apalancamiento aplicado")

cantidad = st.sidebar.number_input("Cantidad BTC", value=0.002, format="%.3f")
tp_precio = st.sidebar.number_input("Take Profit (USDT)", value=0.0, format="%.2f")
sl_precio = st.sidebar.number_input("Stop Loss (USDT)", value=0.0, format="%.2f")

# --- LÓGICA PRINCIPAL ---
precio_actual = client.get_price("BTCUSDT")
st.sidebar.metric("Precio Mercado", f"{precio_actual:,.2f} USDT")
st.sidebar.info(f"Valor a operar: {(cantidad * precio_actual):,.2f} USDT")

posicion = client.get_open_positions("BTCUSDT")
if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    # Cálculo del PNL Flotante en tiempo real
    pnl_flotante = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
    color_pnl = "🟢" if pnl_flotante >= 0 else "🔴"
    
    # Texto enriquecido para el recuadro amarillo
    status_text = (
        f"OPERACIÓN {side} | "
        f"**Entrada:** {entry:,.2f} USDT | "
        f"**PNL:** {color_pnl} {pnl_flotante:,.2f} USDT"
    )
    
    st.warning(status_text)
    
    # Vigilancia automática
    if (side == "LONG" and (tp_precio > 0 and precio_actual >= tp_precio or sl_precio > 0 and precio_actual <= sl_precio)) or \
       (side == "SHORT" and (tp_precio > 0 and precio_actual <= tp_precio or sl_precio > 0 and precio_actual >= sl_precio)):
        lado = "SELL" if side == "LONG" else "BUY"
        client.close_position("BTCUSDT", lado, str(tamano))
        pnl = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
        client.registrar_trade(side, entry, precio_actual, pnl)
        st.error("¡Objetivo alcanzado!"); st.rerun()
else:
    st.success("Sin operaciones abiertas.")

# Botones de Acción
col1, col2, col3 = st.columns(3)
if col1.button("🟢 LONG", key="l"): client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
if col2.button("🔴 SHORT", key="s"): client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()
if col3.button("⛔ CERRAR TODO", key="c"): 
    if posicion: client.close_position("BTCUSDT", "SELL" if float(posicion['positionAmt'])>0 else "BUY", str(abs(float(posicion['positionAmt'])))); st.rerun()

# Historial
st.subheader("📋 Historial")
try: st.table(pd.read_csv("historial_trades.csv").tail(5))
except: st.write("Aún no hay operaciones.")

time.sleep(1)
st.rerun()