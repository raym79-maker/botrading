import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# 1. OBTENCIÓN DE DATOS Y TÍTULO DINÁMICO
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

tendencia = "🟢" if precio_actual > st.session_state.precio_anterior else "🔴" if precio_actual < st.session_state.precio_anterior else "⚪"
st.session_state.precio_anterior = precio_actual

st.set_page_config(page_title=f"{tendencia} ${precio_actual:,.0f} | Bot", layout="wide")

# 2. INICIALIZACIÓN DE ESTADOS
if 'max_price' not in st.session_state: st.session_state.max_price = 0.0
if 'ultima_alerta_vida' not in st.session_state: st.session_state.ultima_alerta_vida = datetime.now()

st.title(f"🤖 Terminal de Control - BTC: ${precio_actual:,.2f}")

# --- PANEL LATERAL (SIDEBAR COMPLETO) ---
with st.sidebar:
    st.header("💰 Cuenta")
    info = client.get_account_status()
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("📡 Diagnóstico del Bot")
    tiempo_restante = timedelta(minutes=30) - (datetime.now() - st.session_state.ultima_alerta_vida)
    minutos_faltantes = int(max(0, tiempo_restante.total_seconds() / 60))
    st.info(f"Próximo reporte en: **{minutos_faltantes} min**")
    
    if rsi > 35 and rsi < 55:
        st.write("🟡 **RSI Neutral:** Esperando fuerza (35 o 55).")
    elif rsi < 35 and precio_actual < ema:
        st.write("🔴 **Filtro EMA:** RSI bajo, pero precio bajo la EMA.")
    elif rsi > 55 and precio_actual > ema:
        st.write("🔴 **Filtro EMA:** RSI alto, pero precio sobre la EMA.")

    st.divider()
    st.header("⚙️ Configuración")
    usdt_riesgo = st.number_input("USDT Margen", value=50.0, step=10.0)
    lev = st.slider("Apalancamiento (x)", 1, 125, 20)
    
    # REINTEGRADO: Take Profit y Stop Loss
    tp_input = st.number_input("Take Profit (Precio)", value=0.0)
    sl_input = st.number_input("Stop Loss (Precio)", value=0.0)
    
    st.divider()
    st.subheader("🛡️ Protecciones")
    use_trailing = st.checkbox("Trailing Stop Activo", value=True)
    distancia_ts = st.number_input("Distancia Trailing (USDT)", value=500.0)
    auto_mode = st.toggle("🚀 MODO AUTO", value=True)
    
    c1, c2 = st.columns(2)
    c1.metric("RSI", f"{rsi:.2f}")
    c2.metric("EMA", f"{int(ema)}")

# --- GRÁFICO ---
components.html(f"""<div style="height:500px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]}});</script><div id="tv_chart"></div></div>""", height=500)

# --- LÓGICA DE POSICIÓN ACTIVA ---
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
        st.warning(f"**POSICIÓN ACTIVA: {side}** | Entrada: **{entry_p:,.2f}** | PNL: {ind} **{pnl_valor:,.4f} USDT** ({pnl_pct:.2f}%)")

        # REINTEGRADO: Cierres por TP/SL
        if (side == "LONG" and ((tp_input > 0 and precio_actual >= tp_input) or (sl_input > 0 and precio_actual <= sl_input))) or \
           (side == "SHORT" and ((tp_input > 0 and precio_actual <= tp_input) or (sl_input > 0 and precio_actual >= sl_input))):
            client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
            client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
            client.enviar_telegram(f"🎯 *CIERRE POR LÍMITE*\nPNL: `{pnl_valor:.2f} USDT`")
            st.rerun()

        # REINTEGRADO: Lógica de Trailing Stop
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
    if precio_actual > 0 and auto_mode and rsi > 0:
        cantidad_op = round((usdt_riesgo * lev) / precio_actual, 3)
        if rsi < 35 and precio_actual > ema:
            client.place_order("BTCUSDT", "BUY", str(cantidad_op))
            client.enviar_telegram(f"🚀 *NUEVA POSICIÓN (LONG)*\nInversión: `{usdt_riesgo} USDT`")
            st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()
        elif rsi > 55 and precio_actual < ema:
            client.place_order("BTCUSDT", "SELL", str(cantidad_op))
            client.enviar_telegram(f"📉 *NUEVA POSICIÓN (SHORT)*\nInversión: `{usdt_riesgo} USDT`")
            st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()

# --- HEARTBEAT INDEPENDIENTE (30 MIN) ---
ahora = datetime.now()
if (ahora - st.session_state.ultima_alerta_vida) > timedelta(minutes=30):
    client.enviar_telegram(f"💓 *CENTINELA ACTIVO*\nBTC: `${precio_actual:,.2f}`\nRSI: `{rsi:.2f}`")
    st.session_state.ultima_alerta_vida = ahora

# --- BOTONES MANUALES ---
st.divider()
c1, c2, c3 = st.columns(3)
cant_m = round((usdt_riesgo * lev) / precio_actual, 3) if precio_actual > 0 else 0
if c1.button("🟢 MANUAL LONG"):
    client.place_order("BTCUSDT", "BUY", str(cant_m))
    client.enviar_telegram(f"🚀 *ENTRADA MANUAL (LONG)*")
    st.session_state.ultima_alerta_vida = ahora ; st.rerun()
if c2.button("🔴 MANUAL SHORT"):
    client.place_order("BTCUSDT", "SELL", str(cant_m))
    client.enviar_telegram(f"📉 *ENTRADA MANUAL (SHORT)*")
    st.session_state.ultima_alerta_vida = ahora ; st.rerun()
if c3.button("⛔ CERRAR POSICIÓN"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
        client.enviar_telegram(f"⛔ *CIERRE MANUAL*\nPNL: `{pnl_valor:.2f} USDT`")
        st.session_state.ultima_alerta_vida = ahora ; st.rerun()

# --- REINTEGRADO: HISTORIAL DE TRADES ---
st.divider()
st.subheader("📋 Historial de Trades (PostgreSQL)")
df = client.obtener_historial_db()
if df is not None and not df.empty:
    st.table(df)
else:
    st.info("Aún no hay trades registrados en el historial.")

time.sleep(2); st.rerun()
