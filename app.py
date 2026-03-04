import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# --- PRE-CÁLCULO PARA EL TÍTULO DINÁMICO ---
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

tendencia_emoji = "🟢" if precio_actual > st.session_state.precio_anterior else "🔴" if precio_actual < st.session_state.precio_anterior else "⚪"
st.session_state.precio_anterior = precio_actual

# Título de la pestaña con precio y emoji
titulo_tab = f"{tendencia_emoji} ${precio_actual:,.0f} | Bot"
st.set_page_config(page_title=titulo_tab, layout="wide")

# --- INICIALIZACIÓN DE ESTADOS ---
if 'max_price' not in st.session_state: 
    st.session_state.max_price = 0.0
if 'ultima_alerta_vida' not in st.session_state:
    st.session_state.ultima_alerta_vida = datetime.now()

st.title(f"🤖 Terminal Pro - BTC: ${precio_actual:,.2f}")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("💰 Cuenta")
    info = client.get_account_status()
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("⚖️ Riesgo")
    lev = st.slider("Apalancamiento (x)", 1, 125, 20)
    if st.button("Aplicar"):
        client.set_leverage("BTCUSDT", lev)
        st.success(f"Ajustado a {lev}x")

    st.divider()
    st.header("⚙️ Config")
    usdt_riesgo = st.number_input("USDT Margen", value=50.0, step=10.0)
    tp_input = st.number_input("Take Profit", value=0.0)
    sl_input = st.number_input("Stop Loss", value=0.0)
    
    st.divider()
    st.subheader("🛡️ Protecciones")
    use_trailing = st.checkbox("Trailing Stop", value=True)
    distancia_ts = st.number_input("Distancia (USDT)", value=500.0)
    
    auto_mode = st.toggle("🚀 AUTO", value=True)
    
    c1, c2 = st.columns(2)
    c1.metric("RSI", f"{rsi if rsi > 0 else '...'}")
    c2.metric("EMA", f"{int(ema) if ema > 0 else '...'}")

# --- GRÁFICO ---
components.html(f"""<div style="height:500px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]}});</script><div id="tv_chart"></div></div>""", height=500)

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
        ind = "🟢" if pnl_valor >= 0 else "🔴"
        st.warning(f"**POSICIÓN ACTIVA: {side}** | PNL: {ind} **{pnl_valor:,.4f} USDT** ({pnl_pct:.2f}%)")

        # Trailing Stop
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
                client.enviar_telegram(f"🚀 *NUEVA POSICIÓN (LONG)*")
                st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()
            elif rsi > 55 and precio_actual < ema:
                client.place_order("BTCUSDT", "SELL", str(cantidad_op))
                client.enviar_telegram(f"📉 *NUEVA POSICIÓN (SHORT)*")
                st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()
            
            # --- HEARTBEAT TEST (1 MINUTO) ---
            tiempo_transcurrido = datetime.now() - st.session_state.ultima_alerta_vida
            if tiempo_transcurrido > timedelta(minutes=1):
                client.enviar_telegram(f"💓 *HEARTBEAT TEST (1 MIN)*\nBTC: `${precio_actual:,.2f}`\nEstado: Vigilando...")
                st.session_state.ultima_alerta_vida = datetime.now()

# --- BOTONES ---
st.divider()
c1, c2, c3 = st.columns(3)
if precio_actual > 0:
    cant_m = round((usdt_riesgo * lev) / precio_actual, 3)

if c1.button("🟢 MANUAL LONG"):
    client.place_order("BTCUSDT", "BUY", str(cant_m))
    client.enviar_telegram(f"🚀 *ENTRADA MANUAL (LONG)*")
    st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()

if c2.button("🔴 MANUAL SHORT"):
    client.place_order("BTCUSDT", "SELL", str(cant_m))
    client.enviar_telegram(f"📉 *ENTRADA MANUAL (SHORT)*")
    st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()

if c3.button("⛔ CERRAR POSICIÓN"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
        client.enviar_telegram(f"⛔ *CIERRE MANUAL*\nPNL: `{pnl_valor:.2f} USDT`")
        st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()

# --- HISTORIAL ---
st.divider()
st.subheader("📋 Historial de Trades (PostgreSQL)")
df = client.obtener_historial_db()
if df is not None and not df.empty: st.table(df)

time.sleep(2); st.rerun()
