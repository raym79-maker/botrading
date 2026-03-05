import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# 1. OBTENCIÓN DE DATOS INICIALES
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

# 2. LÓGICA DE TÍTULO DINÁMICO (PESTAÑA DEL NAVEGADOR)
if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

if precio_actual > st.session_state.precio_anterior:
    tendencia_emoji = "🟢"
elif precio_actual < st.session_state.precio_anterior:
    tendencia_emoji = "🔴"
else:
    tendencia_emoji = "⚪"

st.session_state.precio_anterior = precio_actual
titulo_tab = f"{tendencia_emoji} ${precio_actual:,.0f} | Bot"

st.set_page_config(page_title=titulo_tab, layout="wide")

# 3. INICIALIZACIÓN DE ESTADOS DE SESIÓN
if 'max_price' not in st.session_state: 
    st.session_state.max_price = 0.0
if 'ultima_alerta_vida' not in st.session_state:
    st.session_state.ultima_alerta_vida = datetime.now()

st.title(f"🤖 Terminal Pro - BTC: ${precio_actual:,.2f}")

# --- PANEL LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("💰 Cuenta")
    info = client.get_account_status()
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("⚖️ Riesgo")
    lev = st.slider("Apalancamiento (x)", 1, 125, 20)
    if st.button("Aplicar Apalancamiento"):
        client.set_leverage("BTCUSDT", lev)
        st.success(f"Ajustado a {lev}x")

    st.header("⚙️ Configuración")
    usdt_riesgo = st.number_input("USDT Margen (Inversión)", value=50.0, step=10.0)
    tp_input = st.number_input("Take Profit (Precio)", value=0.0)
    sl_input = st.number_input("Stop Loss (Precio)", value=0.0)
    
    st.divider()
    st.subheader("🛡️ Protecciones")
    use_trailing = st.checkbox("Trailing Stop Activo", value=True)
    distancia_ts = st.number_input("Distancia Trailing (USDT)", value=500.0)
    auto_mode = st.toggle("🚀 ESTRATEGIA AUTO", value=True)
    
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("RSI (14)", f"{rsi:.2f}" if rsi > 0 else "...")
    c2.metric("EMA (20)", f"{int(ema)}" if ema > 0 else "...")

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
        # Cálculo de PNL y ROI
        pnl_valor = (precio_actual - entry_p) * tamano if side == "LONG" else (entry_p - precio_actual) * tamano
        pnl_pct = (pnl_valor / (entry_p * tamano / lev)) * 100 if entry_p > 0 else 0
        ind = "🟢" if pnl_valor >= 0 else "🔴"
        
        # BARRA DE ESTADO CON PRECIO DE ENTRADA
        st.warning(f"**POSICIÓN ACTIVA: {side}** | Entrada: **{entry_p:,.2f}** | PNL: {ind} **{pnl_valor:,.4f} USDT** ({pnl_pct:.2f}%)")

        # GESTIÓN DE CIERRES (TP/SL)
        if (side == "LONG" and ((tp_input > 0 and precio_actual >= tp_input) or (sl_input > 0 and precio_actual <= sl_input))) or \
           (side == "SHORT" and ((tp_input > 0 and precio_actual <= tp_input) or (sl_input > 0 and precio_actual >= sl_input))):
            client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
            client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
            client.enviar_telegram(f"🎯 *CIERRE POR LÍMITE*\nPNL: `{pnl_valor:.2f} USDT`")
            st.rerun()

        # GESTIÓN DE TRAILING STOP
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
    # LÓGICA DE APERTURA AUTOMÁTICA
    st.session_state.max_price = 0
    if precio_actual > 0:
        cantidad_op = round((usdt_riesgo * lev) / precio_actual, 3)
        if auto_mode and rsi > 0:
            if rsi < 35 and precio_actual > ema:
                client.place_order("BTCUSDT", "BUY", str(cantidad_op))
                client.enviar_telegram(f"🚀 *NUEVA POSICIÓN (LONG)*\nInversión: `{usdt_riesgo} USDT`")
                st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()
            elif rsi > 55 and precio_actual < ema:
                client.place_order("BTCUSDT", "SELL", str(cantidad_op))
                client.enviar_telegram(f"📉 *NUEVA POSICIÓN (SHORT)*\nInversión: `{usdt_riesgo} USDT`")
                st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()

# --- LÓGICA DE ALERTA DE VIDA (HEARTBEAT INDEPENDIENTE) ---
ahora = datetime.now()
tiempo_transcurrido = ahora - st.session_state.ultima_alerta_vida

if tiempo_transcurrido > timedelta(hours=3):
    estado_p = "ACTIVA 📈" if posicion else "ESPERANDO 💤"
    client.enviar_telegram(
        f"💓 *CENTINELA: REPORTE DE SALUD*\n"
        f"💰 BTC: `${precio_actual:,.2f}`\n"
        f"📊 RSI: `{rsi:.2f}`\n"
        f"🛡️ Posición: `{estado_p}`\n"
        f"✅ Sistema operativo."
    )
    st.session_state.ultima_alerta_vida = ahora

# --- BOTONES MANUALES ---
st.divider()
c1, c2, c3 = st.columns(3)
if precio_actual > 0:
    cant_m = round((usdt_riesgo * lev) / precio_actual, 3)

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

# --- HISTORIAL ---
st.divider()
st.subheader("📋 Historial de Trades (PostgreSQL)")
df = client.obtener_historial_db()
if df is not None and not df.empty: st.table(df)

time.sleep(2); st.rerun()
