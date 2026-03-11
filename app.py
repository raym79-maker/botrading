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

# Emoji dinámico para la pestaña del navegador (Tendencia visual rápida)
emoji = "🟢" if precio_actual > st.session_state.precio_anterior else "🔴" if precio_actual < st.session_state.precio_anterior else "⚪"
st.session_state.precio_anterior = precio_actual

st.set_page_config(
    page_title=f"{emoji} ${precio_actual:,.0f} | Bot Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialización de la memoria persistente de la sesión (Bot State)
if 'max_price' not in st.session_state: 
    st.session_state.max_price = 0.0
if 'ultima_alerta_vida' not in st.session_state: 
    st.session_state.ultima_alerta_vida = datetime.now()
if 'estado_actual' not in st.session_state: 
    st.session_state.estado_actual = "NEUTRAL"

st.title(f"🤖 Terminal Pro BTC - `${precio_actual:,.2f}`")

# --- 2. PANEL LATERAL (SIDEBAR - CONTROLES Y DIAGNÓSTICO) ---
with st.sidebar:
    st.header("💰 Estado de la Cuenta")
    info = client.get_account_status()
    st.metric("Equity Total", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("📡 Diagnóstico de Señal")
    
    # Heartbeat: Tiempo restante para el próximo reporte de vida en Telegram
    t_restante = timedelta(hours=1) - (datetime.now() - st.session_state.ultima_alerta_vida)
    mins_restantes = int(max(0, t_restante.total_seconds() / 60))
    st.info(f"⌛ Reporte de vida en: **{mins_restantes} min**")
    
    # Lógica de detección de estados de mercado para alarmas
    nuevo_est = "NEUTRAL"
    if rsi <= 35 and rsi > 0:
        if precio_actual > ema:
            nuevo_est = "OPORTUNIDAD_LONG"
            st.success(f"🎯 **LONG:** RSI ({rsi:.2f}) y sobre EMA.")
        else:
            nuevo_est = "FILTRO_LONG"
            st.warning("🔴 RSI bajo, pero bajo la EMA (Tendencia bajista)")
    elif rsi >= 55:
        if precio_actual < ema:
            nuevo_est = "OPORTUNIDAD_SHORT"
            st.success(f"🎯 **SHORT:** RSI ({rsi:.2f}) y bajo EMA.")
        else:
            nuevo_est = "FILTRO_SHORT"
            st.warning("🔴 RSI alto, pero sobre la EMA (Tendencia alcista)")

    # Envío automático de Telegram solo por cambio de estado real
    if nuevo_est != st.session_state.estado_actual:
        if "OPORTUNIDAD" in nuevo_est:
            client.enviar_telegram(f"🎯 Alerta: {nuevo_est} | RSI: {rsi} | Precio: {precio_actual}")
        st.session_state.estado_actual = nuevo_est

    st.divider()
    st.header("⚙️ Ajustes de Estrategia")
    riesgo = st.number_input("Inversión USDT (Margen)", value=50.0, step=10.0)
    lev = st.slider("Apalancamiento (x)", 1, 125, 20)
    tp_p = st.number_input("Take Profit (Precio de salida)", value=0.0)
    sl_p = st.number_input("Stop Loss (Precio de seguridad)", value=0.0)
    
    st.divider()
    st.subheader("🛡️ Protecciones Activas")
    use_ts = st.checkbox("Trailing Stop", value=True)
    dist_ts = st.number_input("Distancia TS (USDT)", value=500.0)
    auto_mode = st.toggle("🚀 MODO AUTO (24/7)", value=True)
    
    # Indicadores en tiempo real al final del sidebar
    col_ind1, col_ind2 = st.columns(2)
    col_ind1.metric("RSI (14)", f"{rsi:.2f}")
    col_ind2.metric("EMA (20)", f"{int(ema)}")

# --- 3. GRÁFICO PROFESIONAL TRADINGVIEW ---
components.html(f"""
    <div style="height:480px;">
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark",
          "container_id": "tv_chart", "style": "1", "toolbar_bg": "#f1f3f6",
          "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": true,
          "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]
        }});
        </script><div id="tv_chart"></div>
    </div>
    """, height=480)

# --- 4. GESTIÓN DE POSICIÓN ACTIVA Y LÓGICA DE CIERRE ---
pos = client.get_open_positions("BTCUSDT")
pnl_v = 0.0

if pos:
    # Identificación de la dirección de la posición
    side = "LONG" if float(pos['positionAmt']) > 0 else "SHORT"
    ent = float(pos['entryPrice'])
    tam = abs(float(pos['positionAmt']))
    
    # Cálculo de PNL y ROI Porcentual Real
    pnl_v = (precio_actual - ent) * tam if side == "LONG" else (ent - precio_actual) * tam
    pnl_p = (pnl_v / (ent * tam / lev)) * 100 if ent > 0 else 0
    
    # INDICADOR VISUAL DE COLOR PARA PNL (🟢 para Ganancia / 🔴 para Pérdida)
    indicador_color = "🟢" if pnl_v >= 0 else "🔴"
    
    st.warning(f"⚠️ **{side} ACTIVO** | Entrada: `${ent:,.2f}` | PNL: {indicador_color} **{pnl_v:.4f} USDT** ({pnl_p:.2f}%)")

    # A. Cierres Automáticos por Take Profit o Stop Loss
    if (side == "LONG" and ((tp_p > 0 and precio_actual >= tp_p) or (sl_p > 0 and precio_actual <= sl_p))) or \
       (side == "SHORT" and ((tp_p > 0 and precio_actual <= tp_p) or (sl_p > 0 and precio_actual >= sl_p))):
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tam))
        client.registrar_trade(side, ent, precio_actual, pnl_v)
        st.rerun()

    # B. Lógica de Trailing Stop (Seguimiento de Máximos/Mínimos)
    if use_ts:
        if st.session_state.max_price == 0: 
            st.session_state.max_price = precio_actual
            
        if side == "LONG":
            if precio_actual > st.session_state.max_price: 
                st.session_state.max_price = precio_actual
            if precio_actual <= (st.session_state.max_price - dist_ts):
                client.place_order("BTCUSDT", "SELL", str(tam))
                client.registrar_trade(side, ent, precio_actual, pnl_v)
                st.session_state.max_price = 0
                st.rerun()
        else:
            if st.session_state.max_price == 0 or precio_actual < st.session_state.max_price: 
                st.session_state.max_price = precio_actual
            if precio_actual >= (st.session_state.max_price + dist_ts):
                client.place_order("BTCUSDT", "BUY", str(tam))
                client.registrar_trade(side, ent, precio_actual, pnl_v)
                st.session_state.max_price = 0
                st.rerun()
else:
    # Lógica de Apertura Automática (Modo Auto)
    st.session_state.max_price = 0
    if auto_mode and rsi > 0:
        cant_op = round((riesgo * lev) / precio_actual, 3)
        if rsi <= 35 and precio_actual > ema:
            client.place_order("BTCUSDT", "BUY", str(cant_op))
            st.rerun()
        elif rsi >= 55 and precio_actual < ema:
            client.place_order("BTCUSDT", "SELL", str(cant_op))
            st.rerun()

# --- 5. CONTROLES MANUALES ---
st.divider()
col_m1, col_m2, col_m3 = st.columns(3)
cant_manual = round((riesgo * lev) / precio_actual, 3) if precio_actual > 0 else 0

if col_m1.button("🟢 ABRIR LONG MANUAL", use_container_width=True):
    client.place_order("BTCUSDT", "BUY", str(cant_manual))
    st.rerun()
    
if col_m2.button("🔴 ABRIR SHORT MANUAL", use_container_width=True):
    client.place_order("BTCUSDT", "SELL", str(cant_manual))
    st.rerun()
    
if col_m3.button("⛔ CERRAR POSICIÓN AHORA", use_container_width=True):
    if pos:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tam))
        client.registrar_trade(side, ent, precio_actual, pnl_v)
        st.rerun()

# --- 6. HISTORIAL DE BASE DE DATOS Y HEARTBEAT ---
st.divider()
st.subheader("📋 Historial de Trades (PostgreSQL)")
df_historial = client.obtener_historial_db()

if df_historial is not None and not df_historial.empty:
    st.table(df_historial)
else:
    st.info("Sin registros de trades recientes en la base de datos.")

# Envío de reporte de vida (Centinela) cada hora
if (datetime.now() - st.session_state.ultima_alerta_vida) > timedelta(hours=1):
    client.enviar_telegram(f"💓 *CENTINELA ACTIVO*\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`")
    st.session_state.ultima_alerta_vida = datetime.now()

# Bucle de refresco automático
time.sleep(10)
st.rerun()
