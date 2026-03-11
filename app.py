import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# 1. SETUP DE DATOS Y ESTADO DE SESIÓN
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

# Tendencia dinámica para la pestaña
tendencia = "🟢" if precio_actual > st.session_state.precio_anterior else "🔴"
st.session_state.precio_anterior = precio_actual

st.set_page_config(page_title=f"{tendencia} ${precio_actual:,.0f} | Bot", layout="wide")

# Inicialización de la memoria del bot
if 'max_price' not in st.session_state: 
    st.session_state.max_price = 0.0
if 'ultima_alerta_vida' not in st.session_state: 
    st.session_state.ultima_alerta_vida = datetime.now()
if 'estado_actual' not in st.session_state: 
    st.session_state.estado_actual = "NEUTRAL"

st.title(f"🤖 Terminal Pro BTC - Precio: `${precio_actual:,.2f}`")

# --- 2. PANEL LATERAL (DIAGNÓSTICO Y RIESGO) ---
with st.sidebar:
    st.header("💰 Cuenta")
    info = client.get_account_status()
    st.metric("Equity Total", f"{info['equity']:,.2f} USDT", 
              delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("📡 Diagnóstico y Alarmas")
    
    t_restante = timedelta(hours=1) - (datetime.now() - st.session_state.ultima_alerta_vida)
    mins = int(max(0, t_restante.total_seconds() / 60))
    st.info(f"⌛ Reporte de vida en: **{mins} min**")
    
    # Lógica de estados para Diagnóstico
    nuevo_est = "NEUTRAL"
    msg_diag = f"🟡 RSI Neutral ({rsi:.2f})"

    if rsi <= 35 and rsi > 0:
        if precio_actual > ema:
            nuevo_est = "OPORTUNIDAD_LONG"
            msg_diag = f"🎯 **LONG:** RSI ({rsi:.2f}) y sobre EMA."
            st.success(msg_diag)
        else:
            nuevo_est = "FILTRO_LONG"
            st.warning("🔴 RSI bajo, pero bajo la EMA")
    elif rsi >= 55:
        if precio_actual < ema:
            nuevo_est = "OPORTUNIDAD_SHORT"
            msg_diag = f"🎯 **SHORT:** RSI ({rsi:.2f}) y bajo EMA."
            st.success(msg_diag)
        else:
            nuevo_est = "FILTRO_SHORT"
            st.warning("🔴 RSI alto, pero sobre la EMA")

    if nuevo_est != st.session_state.estado_actual:
        if "OPORTUNIDAD" in nuevo_est: client.enviar_telegram(msg_diag)
        st.session_state.estado_actual = nuevo_est

    st.divider()
    st.header("⚙️ Configuración")
    riesgo = st.number_input("Inversión USDT", value=50.0)
    lev = st.slider("Apalancamiento", 1, 125, 20)
    tp_p = st.number_input("Take Profit", value=0.0)
    sl_p = st.number_input("Stop Loss", value=0.0)
    
    st.divider()
    st.subheader("🛡️ Protecciones")
    use_ts = st.checkbox("Trailing Stop", value=True)
    dist_ts = st.number_input("Distancia (USDT)", value=500.0)
    auto = st.toggle("🚀 MODO AUTO", value=True)
    
    # SENSORES DE MERCADO (EMA Y RSI)
    c1, c2 = st.columns(2)
    c1.metric("RSI", f"{rsi:.2f}")
    c2.metric("EMA", f"{int(ema)}")

# --- 3. GRÁFICO TRADINGVIEW ---
components.html(f"""<div style="height:480px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]}});</script><div id="tv_chart"></div></div>""", height=480)

# --- 4. GESTIÓN DE POSICIÓN ACTIVA ---
pos = client.get_open_positions("BTCUSDT")
pnl_v = 0.0

if pos:
    side = "LONG" if float(pos['positionAmt']) > 0 else "SHORT"
    ent, tam = float(pos['entryPrice']), abs(float(pos['positionAmt']))
    pnl_v = (precio_actual - ent) * tam if side == "LONG" else (ent - precio_actual) * tam
    pnl_p = (pnl_v / (ent * tam / lev)) * 100 if ent > 0 else 0
    st.warning(f"⚠️ **{side} ACTIVO** | Entrada: `${ent:,.2f}` | PNL: **{pnl_v:.4f} USDT** ({pnl_p:.2f}%)")

    # Cierres automáticos por TP/SL
    if (side == "LONG" and ((tp_p > 0 and precio_actual >= tp_p) or (sl_p > 0 and precio_actual <= sl_p))) or \
       (side == "SHORT" and ((tp_p > 0 and precio_actual <= tp_p) or (sl_p > 0 and precio_actual >= sl_p))):
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tam))
        client.registrar_trade(side, ent, precio_actual, pnl_v)
        st.rerun()

    # Lógica de Trailing Stop
    if use_ts:
        if st.session_state.max_price == 0: st.session_state.max_price = precio_actual
        if side == "LONG":
            if precio_actual > st.session_state.max_price: st.session_state.max_price = precio_actual
            if precio_actual <= (st.session_state.max_price - dist_ts):
                client.place_order("BTCUSDT", "SELL", str(tam))
                client.registrar_trade(side, ent, precio_actual, pnl_v); st.session_state.max_price = 0; st.rerun()
        else:
            if st.session_state.max_price == 0 or precio_actual < st.session_state.max_price: st.session_state.max_price = precio_actual
            if precio_actual >= (st.session_state.max_price + dist_ts):
                client.place_order("BTCUSDT", "BUY", str(tam))
                client.registrar_trade(side, ent, precio_actual, pnl_v); st.session_state.max_price = 0; st.rerun()
else:
    st.session_state.max_price = 0
    if auto and rsi > 0:
        cant = round((riesgo * lev) / precio_actual, 3)
        if rsi <= 35 and precio_actual > ema:
            client.place_order("BTCUSDT", "BUY", str(cant)); st.rerun()
        elif rsi >= 55 and precio_actual < ema:
            client.place_order("BTCUSDT", "SELL", str(cant)); st.rerun()

# --- 5. CONTROLES MANUALES ---
st.divider()
c1, c2, c3 = st.columns(3)
cant_m = round((riesgo * lev) / precio_actual, 3) if precio_actual > 0 else 0
if c1.button("🟢 MANUAL LONG", use_container_width=True):
    client.place_order("BTCUSDT", "BUY", str(cant_m)); st.rerun()
if c2.button("🔴 MANUAL SHORT", use_container_width=True):
    client.place_order("BTCUSDT", "SELL", str(cant_m)); st.rerun()
if c3.button("⛔ CERRAR POSICIÓN", use_container_width=True):
    if pos:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tam))
        client.registrar_trade(side, ent, precio_actual, pnl_v); st.rerun()

st.divider()
st.subheader("📋 Historial de Trades (PostgreSQL)")
df = client.obtener_historial_db()
if df is not None and not df.empty: st.table(df)

if (datetime.now() - st.session_state.ultima_alerta_vida) > timedelta(hours=1):
    client.enviar_telegram(f"💓 *CENTINELA ACTIVO*\nBTC: `${precio_actual:,.2f}`")
    st.session_state.ultima_alerta_vida = datetime.now()

time.sleep(10); st.rerun()
