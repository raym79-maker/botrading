import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# ==========================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==========================================
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

# Gestión de tendencia en pestaña
if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

emoji_p = "🟢" if precio_actual >= st.session_state.precio_anterior else "🔴"
st.session_state.precio_anterior = precio_actual

st.set_page_config(
    page_title=f"{emoji_p} ${precio_actual:,.0f} | Terminal Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialización de estados persistentes
if 'max_price' not in st.session_state: st.session_state.max_price = 0.0
if 'ultima_alerta' not in st.session_state: st.session_state.ultima_alerta = datetime.now()
if 'estado_actual' not in st.session_state: st.session_state.estado_actual = "NEUTRAL"

# Estilo visual para métricas
st.markdown("""<style>
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    </style>""", unsafe_allow_html=True)

st.title(f"🤖 Terminal Pro BTC - `${precio_actual:,.2f}`")

# ==========================================
# 2. PANEL LATERAL (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("💰 Estado de Cuenta")
    acc = client.get_account_status()
    
    if acc.get('error'):
        st.error(f"🚨 Error: {acc['error']}")
        st.info("💡 Verifica BINANCE_API_SECRET e IS_TESTNET en Railway.")
    else:
        st.metric("Balance Equity", f"{acc['equity']:,.2f} USDT", 
                  delta=f"{acc['unrealized_pnl']:,.2f} PNL")
        st.success(f"🔗 Modo: {'DEMO' if client.is_testnet else 'REAL'}")

    st.divider()
    st.header("📡 Diagnóstico de Señal")
    
    # Contador para reporte de Telegram (1h)
    t_rest = timedelta(hours=1) - (datetime.now() - st.session_state.ultima_alerta)
    st.info(f"⌛ Reporte en: **{int(max(0, t_rest.total_seconds() / 60))} min**")
    
    dist_ema = abs(precio_actual - ema)
    nuevo_est = "NEUTRAL"

    # Lógica de Semáforo RSI + EMA
    if 35 < rsi < 55:
        st.write(f"🟡 **Neutral ({rsi:.2f})**")
        st.write(f"Distancia EMA: `${dist_ema:,.2f}`")
    elif rsi <= 35:
        if precio_actual > ema:
            nuevo_est = "OPORTUNIDAD_LONG"
            st.success("🎯 **¡OPORTUNIDAD LONG!**")
        else:
            nuevo_est = "FILTRO_LONG"
            st.warning("🔴 **Filtro: Bajo EMA**")
    elif rsi >= 55:
        if precio_actual < ema:
            nuevo_est = "OPORTUNIDAD_SHORT"
            st.success("🎯 **¡OPORTUNIDAD SHORT!**")
        else:
            nuevo_est = "FILTRO_SHORT"
            st.warning("🔴 **Filtro: Sobre EMA**")

    # Notificación por cambio de tendencia
    if nuevo_est != st.session_state.estado_actual:
        client.enviar_telegram(f"📢 Cambio: {nuevo_est} | BTC: `${precio_actual:,.2f}`")
        st.session_state.estado_actual = nuevo_est

    st.divider()
    st.header("⚙️ Ajustes de Riesgo")
    riesgo = st.number_input("Inversión USDT", value=50.0, step=10.0)
    lev = st.slider("Apalancamiento", 1, 125, 20)
    auto = st.toggle("🚀 MODO AUTOMÁTICO", value=True)

# ==========================================
# 3. GRÁFICO PROFESIONAL
# ==========================================

components.html(f"""
    <div style="height:480px;">
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark",
          "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]
        }});
        </script>
        <div id="tv_chart"></div>
    </div>
    """, height=480)

# ==========================================
# 4. GESTIÓN DE POSICIÓN ACTIVA
# ==========================================
pos = client.get_open_positions()

if pos:
    lado = "LONG" if float(pos['positionAmt']) > 0 else "SHORT"
    ent = float(pos['entryPrice'])
    tam = abs(float(pos['positionAmt']))
    
    # Cálculo de PNL y ROI
    pnl = (precio_actual - ent) * tam if lado == "LONG" else (ent - precio_actual) * tam
    roi = (pnl / (ent * tam / lev)) * 100 if ent > 0 else 0
    ind = "🟢" if pnl >= 0 else "🔴"
    
    st.warning(f"⚠️ **POSICIÓN {lado} ACTIVA**")
    c1, c2, c3 = st.columns(3)
    c1.metric("Entrada", f"${ent:,.2f}")
    c2.metric("PNL", f"{ind} {pnl:.2f} USDT")
    c3.metric("ROI", f"{roi:.2f}%")
    
    if st.button("⛔ CERRAR POSICIÓN AHORA", use_container_width=True):
        client.place_order("BTCUSDT", "SELL" if lado == "LONG" else "BUY", str(tam))
        client.registrar_trade(lado, ent, precio_actual, pnl)
        st.rerun()
else:
    # Controles manuales si no hay trade abierto
    st.info("🔎 Buscando entradas... Operar manualmente:")
    cm1, cm2 = st.columns(2)
    qty_m = round((riesgo * lev) / precio_actual, 3) if precio_actual > 0 else 0
    
    if cm1.button("🟢 ABRIR LONG MANUAL", use_container_width=True):
        if qty_m > 0:
            client.place_order("BTCUSDT", "BUY", qty_m)
            st.rerun()
    
    if cm2.button("🔴 ABRIR SHORT MANUAL", use_container_width=True):
        if qty_m > 0:
            client.place_order("BTCUSDT", "SELL", qty_m)
            st.rerun()

# ==========================================
# 5. HISTORIAL DE POSTGRESQL
# ==========================================
st.divider()
st.subheader("📋 Historial de Operaciones")
df_h = client.obtener_historial_db()

if df_h is not None and not df_h.empty:
    st.table(df_h)
else:
    st.write("Esperando el primer trade para mostrar el historial...")

# ==========================================
# 6. HEARTBEAT Y REFRESCO
# ==========================================
if (datetime.now() - st.session_state.ultima_alerta) > timedelta(hours=1):
    client.enviar_telegram(f"💓 Bot Activo | BTC: `${precio_actual:,.2f}`")
    st.session_state.ultima_alerta = datetime.now()

time.sleep(10)
st.rerun()
