import streamlit as st
import time, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Bot Trading Automático", layout="wide")
client = BinanceClient()

st.title("🤖 Terminal Trading Auto-RSI+EMA")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("💰 Cuenta")
    info = client.get_account_status() if hasattr(client, 'get_account_status') else {'equity':0, 'unrealized_pnl':0, 'wallet':0}
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    auto_mode = st.toggle("🚀 ACTIVAR ESTRATEGIA AUTO")
    
    st.header("⚙️ Configuración")
    cantidad = st.number_input("CANTIDAD BTC", value=0.002, format="%.3f")
    
    rsi, ema, precio_actual = client.get_indicators()
    
    # Visualización de indicadores en barra lateral
    c1, c2 = st.columns(2)
    c1.metric("RSI (14)", f"{rsi if rsi > 0 else 'Cargando'}")
    c2.metric("EMA (20)", f"{ema if ema > 0 else 'Cargando'}")
    st.metric("Precio Actual", f"{precio_actual:,.2f} USDT")

# --- GRÁFICO CON INDICADORES VISIBLES ---
# He añadido 'EMA' y 'RSI' a la lista de 'studies'
components.html(f"""
<div style="height:450px;">
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true,
    "symbol": "BINANCE:BTCUSDT",
    "interval": "15",
    "theme": "dark",
    "style": "1",
    "locale": "es",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "hide_top_toolbar": false,
    "save_image": false,
    "container_id": "tv_chart",
    "studies": [
      "RSI@tv-basicstudies",
      "Moving Average Exponential@tv-basicstudies"
    ]
  }});
  </script>
  <div id="tv_chart"></div>
</div>
""", height=450)

# --- LÓGICA DE ESTRATEGIA ---
posicion = client.get_open_positions("BTCUSDT")

if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    if precio_actual > 0:
        pnl = (precio_actual - entry) * tamano if side == "LONG" else (entry - precio_actual) * tamano
        st.warning(f"**POSICIÓN ACTIVA: {side}** | PNL: {'🟢' if pnl >= 0 else '🔴'} {pnl:,.4f} USDT")
else:
    # SI AUTO_MODE ESTÁ ON Y NO HAY POSICIÓN: BUSCAR ENTRADA
    if auto_mode and rsi > 0 and precio_actual > 0:
        st.info("🤖 Bot buscando entrada...")
        
        # REGLA LONG: RSI sobrevendido (<35) y precio cruza arriba de EMA 20
        if rsi < 35 and precio_actual > ema:
            st.success("🎯 SEÑAL LONG DETECTADA")
            client.place_order("BTCUSDT", "BUY", str(cantidad))
            st.rerun()
            
        # REGLA SHORT: RSI sobrecomprado (>65) y precio cruza abajo de EMA 20
        elif rsi > 65 and precio_actual < ema:
            st.success("🎯 SEÑAL SHORT DETECTADA")
            client.place_order("BTCUSDT", "SELL", str(cantidad))
            st.rerun()

# --- BOTONES MANUALES ---
st.divider()
col1, col2, col3 = st.columns(3)
if col1.button("🟢 FORZAR LONG"): client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
if col2.button("🔴 FORZAR SHORT"): client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()
if col3.button("⛔ CERRAR Y REGISTRAR"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side=="LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry, precio_actual, pnl)
        st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial Permanente (DB)")
df = client.obtener_historial_db()
if df is not None and not df.empty: st.table(df)

time.sleep(2); st.rerun()
