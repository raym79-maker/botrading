import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# =========================================================
# 1. CONFIGURACIÓN Y ESTILO DE LA INTERFAZ
# =========================================================
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

# Gestión del título dinámico en la pestaña del navegador
if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

emoji_web = "🟢" if precio_actual >= st.session_state.precio_anterior else "🔴"
st.session_state.precio_anterior = precio_actual

st.set_page_config(
    page_title=f"{emoji_web} ${precio_actual:,.0f} | Terminal Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialización de variables de estado de sesión
if 'estado_actual' not in st.session_state: 
    st.session_state.estado_actual = "NEUTRAL"
if 'ultima_alerta_vida' not in st.session_state: 
    st.session_state.ultima_alerta_vida = datetime.now()

# Estilo CSS para mejorar el contraste del Dashboard
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    div[data-testid="stMetricValue"] { color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

st.title(f"🤖 Terminal Pro BTC - `${precio_actual:,.2f}`")

# =========================================================
# 2. PANEL LATERAL (SIDEBAR) - CUENTA Y RIESGO
# =========================================================
with st.sidebar:
    st.header("💰 Estado de Cuenta")
    acc = client.get_account_status()
    
    if acc.get('error'):
        st.error(f"🚨 Error API: {acc['error']}")
        st.info("💡 Verifica tus API Keys y que IS_TESTNET coincida con tu cuenta.")
    else:
        st.metric("Balance Equity", f"{acc['equity']:,.2f} USDT", 
                  delta=f"{acc['unrealized_pnl']:,.2f} PNL")
        st.success(f"🔗 Conectado a: {'DEMO' if client.is_testnet else 'REAL'}")

    st.divider()
    
    st.header("📡 Sensores de Mercado")
    dist_ema = abs(precio_actual - ema)
    nuevo_est = "NEUTRAL"

    # Lógica de Semáforo de Trading (Doble Filtro: RSI + EMA)
    if 35 < rsi < 55:
        st.write(f"🟡 **Estado: Neutral ({rsi:.2f})**")
        st.caption(f"Distancia EMA: `${dist_ema:,.2f}`")
    elif rsi <= 35:
        if precio_actual > ema:
            nuevo_est = "OPORTUNIDAD_LONG"
            st.success("🎯 **¡OPORTUNIDAD LONG!**")
        else:
            nuevo_est = "FILTRO_LONG"
            st.warning("🔴 **Filtro: Precio bajo EMA**")
    elif rsi >= 55:
        if precio_actual < ema:
            nuevo_est = "OPORTUNIDAD_SHORT"
            st.success("🎯 **¡OPORTUNIDAD SHORT!**")
        else:
            nuevo_est = "FILTRO_SHORT"
            st.warning("🔴 **Filtro: Precio sobre EMA**")

    # Notificación por Telegram si el estado cambia
    if nuevo_est != st.session_state.estado_actual:
        client.enviar_telegram(f"📢 *Cambio de Señal:* {nuevo_est}\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`")
        st.session_state.estado_actual = nuevo_est

    st.divider()
    st.header("⚙️ Ajustes de Riesgo")
    riesgo_usdt = st.number_input("Inversión USDT", value=50.0, step=10.0)
    apalancamiento = st.slider("Apalancamiento (X)", 1, 125, 20)
    auto_mode = st.toggle("🚀 MODO AUTO", value=True)

# =========================================================
# 3. GRÁFICO PROFESIONAL DE TRADINGVIEW
# =========================================================
components.html(f"""
    <div style="height:480px;">
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15",
          "theme": "dark", "style": "1", "locale": "es", "container_id": "tv_chart",
          "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]
        }});
        </script>
        <div id="tv_chart"></div>
    </div>
    """, height=480)

# =========================================================
# 4. GESTIÓN DE POSICIONES (PNL Y ROI)
# =========================================================
pos = client.get_open_positions()

if pos:
    lado = "LONG" if float(pos['positionAmt']) > 0 else "SHORT"
    ent = float(pos['entryPrice'])
    tam = abs(float(pos['positionAmt']))
    
    # Cálculo de PNL y ROI Porcentual
    if lado == "LONG":
        pnl_val = (precio_actual - ent) * tam
    else:
        pnl_val = (ent - precio_actual) * tam
        
    roi_val = (pnl_val / (ent * tam / apalancamiento)) * 100 if ent > 0 else 0
    ind_color = "🟢" if pnl_val >= 0 else "🔴"
    
    st.warning(f"⚠️ **POSICIÓN {lado} ACTIVA**")
    m1, m2, m3 = st.columns(3)
    m1.metric("Entrada", f"${ent:,.2f}")
    m2.metric("PNL", f"{ind_color} {pnl_val:.2f} USDT")
    m3.metric("ROI %", f"{roi_val:.2f}%")
    
    if st.button("⛔ CERRAR POSICIÓN TOTAL", use_container_width=True):
        client.place_order("BTCUSDT", "SELL" if lado == "LONG" else "BUY", str(tam))
        client.registrar_trade(lado, ent, precio_actual, pnl_val)
        st.rerun()
else:
    # Controles manuales si no hay posición
    st.info("🔎 **Mercado sin posiciones.** Operar manualmente:")
    cm1, cm2 = st.columns(2)
    qty_manual = round((riesgo_usdt * apalancamiento) / precio_actual, 3) if precio_actual > 0 else 0
    
    if cm1.button("🟢 ABRIR LONG MANUAL", use_container_width=True):
        client.place_order("BTCUSDT", "BUY", qty_manual)
        st.rerun()
    if cm2.button("🔴 ABRIR SHORT MANUAL", use_container_width=True):
        client.place_order("BTCUSDT", "SELL", qty_manual)
        st.rerun()

# =========================================================
# 5. HISTORIAL DE TRADES (POSTGRESQL)
# =========================================================
st.divider()
st.subheader("📋 Historial de Operaciones")
df_hist = client.obtener_historial_db()

if df_hist is not None and not df_hist.empty:
    st.table(df_hist)
else:
    st.caption("Buscando registros en PostgreSQL...")

# =========================================================
# 6. HEARTBEAT Y AUTO-REFRESCO
# =========================================================
if (datetime.now() - st.session_state.ultima_alerta_vida) > timedelta(hours=1):
    client.enviar_telegram(f"💓 *Terminal Activa:* BTC `${precio_actual:,.2f}`")
    st.session_state.ultima_alerta_vida = datetime.now()

# Bucle de refresco cada 10 segundos
time.sleep(10)
st.rerun()
