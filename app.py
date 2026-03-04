import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# --- PRE-CÁLCULO PARA EL TÍTULO DINÁMICO ---
# Instanciamos el cliente antes de configurar la página para obtener el precio
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

# Configuramos la página con el precio en el título
# El formato :,.0f mostrará el precio como "72,654" para que sea legible en la pestaña
titulo_tab = f"Bot ${precio_actual:,.0f}" if precio_actual > 0 else "Bot Conectando..."
st.set_page_config(page_title=titulo_tab, layout="wide")

# --- INICIALIZACIÓN DE ESTADOS ---
if 'max_price' not in st.session_state: 
    st.session_state.max_price = 0.0
if 'ultima_alerta_vida' not in st.session_state:
    st.session_state.ultima_alerta_vida = datetime.now()

st.title(f"🤖 Terminal Trading - {titulo_tab}")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("💰 Estado de Cuenta")
    info = client.get_account_status()
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("⚖️ Gestión de Riesgo")
    lev = st.slider("Apalancamiento (x)", 1, 125, 20)
    if st.button("Aplicar Apalancamiento"):
        client.set_leverage("BTCUSDT", lev)
        st.success(f"Ajustado a {lev}x")

    st.divider()
    st.header("⚙️ Configuración")
    usdt_riesgo = st.number_input("USDT POR OPERACIÓN (Margen)", value=50.0, step=10.0)
    tp_input = st.number_input("Take Profit (Precio)", value=0.0)
    sl_input = st.number_input("Stop Loss (Precio)", value=0.0)
    
    st.divider()
    st.subheader("🛡️ Protecciones Dinámicas")
    use_trailing = st.checkbox("Activar Trailing Stop", value=True)
    distancia_ts = st.number_input("Distancia Trailing (USDT)", value=500.0)
    
    st.divider()
    auto_mode = st.toggle("🚀 ESTRATEGIA AUTO", value=True)
    
    # Mostramos los indicadores en el sidebar
    c1, c2 = st.columns(2)
    c1.metric("RSI (14)", f"{rsi if rsi > 0 else '...'}")
    c2.metric("EMA (20)", f"{ema if ema > 0 else '...'}")
    st.metric("BTC Precio Actual", f"{precio_actual:,.2f} USDT")

# --- GRÁFICO ---
components.html(f"""<div style="height:600px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]}});</script><div id="tv_chart"></div></div>""", height=600)

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")
pnl_valor = 0.0

if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry_p = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    if precio_actual > 0:
        pnl_valor = (precio_actual - entry_p) * tamano if side == "LONG" else (entry_p - precio_actual) * tamano
        pnl_pct = (pnl_valor / (entry_p * tamano / lev)) * 100 if entry_p > 0 else 0
        indicador = "🟢" if pnl_valor >= 0 else "🔴"
        st.warning(f"**POSICIÓN ACTIVA: {side}** | Entrada: **{entry_p:,.2f}** | PNL: {indicador} **{pnl_valor:,.4f} USDT** ({pnl_pct:.2f}%)")

        if use_trailing:
            if st.session_state.max_price == 0: st.session_state.max_price = precio_actual
            if side == "LONG":
                if precio_actual > st.session_state.max_price: st.session_state.max_price = precio_actual
                if precio_actual <= (st.session_state.max_price - distancia_ts):
                    client.place_order("BTCUSDT", "SELL", str(tamano))
                    client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
                    client.enviar_telegram(f"🛡️ *CIERRE TRAILING (LONG)*\nPNL: `{pnl_valor:.2f} USDT`")
                    st.session_state.max_price = 0 ; st.rerun()
            else:
                if st.session_state.max_price == 0 or precio_actual < st.session_state.max_price: st.session_state.max_price = precio_actual
                if precio_actual >= (st.session_state.max_price + distancia_ts):
                    client.place_order("BTCUSDT", "BUY", str(tamano))
                    client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
                    client.enviar_telegram(f"🛡️ *CIERRE TRAILING (SHORT)*\nPNL: `{pnl_valor:.2f} USDT`")
                    st.session_state.max_price = 0 ; st.rerun()

else:
    st.session_state.max_price = 0
    if precio_actual > 0:
        cantidad_op = round((usdt_riesgo * lev) / precio_actual, 3)
        
        if auto_mode and rsi > 0:
            if rsi < 35 and precio_actual > ema:
                client.place_order("BTCUSDT", "BUY", str(cantidad_op))
                client.enviar_telegram(f"🚀 *NUEVA POSICIÓN (LONG)*\nInversión: `{usdt_riesgo} USDT`")
                st.session_state.ultima_alerta_vida = datetime.now()
                st.rerun()
            elif rsi > 55 and precio_actual < ema:
                client.place_order("BTCUSDT", "SELL", str(cantidad_op))
                client.enviar_telegram(f"📉 *NUEVA POSICIÓN (SHORT)*\nInversión: `{usdt_riesgo} USDT`")
                st.session_state.ultima_alerta_vida = datetime.now()
                st.rerun()
            
            # --- HEARTBEAT CADA 3 HORAS ---
            tiempo_transcurrido = datetime.now() - st.session_state.ultima_alerta_vida
            if tiempo_transcurrido > timedelta(hours=3):
                client.enviar_telegram(f"💓 *HEARTBEAT: BOT ACTIVO*\nBTC: `${precio_actual:,.2f}`\nRSI: `{rsi:.2f}`")
                st.session_state.ultima_alerta_vida = datetime.now()

# --- BOTONES ---
st.divider()
c1, c2, c3 = st.columns(3)
if precio_actual > 0:
    cantidad_manual = round((usdt_riesgo * lev) / precio_actual, 3)

if c1.button("🟢 MANUAL LONG"):
    client.place_order("BTCUSDT", "BUY", str(cantidad_manual))
    client.enviar_telegram(f"🚀 *ENTRADA MANUAL (LONG)*")
    st.session_state.ultima_alerta_vida = datetime.now()
    st.rerun()

if c2.button("🔴 MANUAL SHORT"):
    client.place_order("BTCUSDT", "SELL", str(cantidad_manual))
    client.enviar_telegram(f"📉 *ENTRADA MANUAL (SHORT)*")
    st.session_state.ultima_alerta_vida = datetime.now()
    st.rerun()

if c3.button("⛔ CERRAR POSICIÓN"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
        client.enviar_telegram(f"⛔ *CIERRE MANUAL*\nPNL: `{pnl_valor:.2f} USDT`")
        st.session_state.ultima_alerta_vida = datetime.now()
        st.rerun()

# --- HISTORIAL ---
st.divider()
st.subheader("📋 Historial de Trades (PostgreSQL)")
df = client.obtener_historial_db()
if df is not None and not df.empty: st.table(df)

time.sleep(2); st.rerun()
