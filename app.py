import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# ==============================================================================
# 1. CONFIGURACIÓN INICIAL DE LA PÁGINA
# ==============================================================================
# Inicializamos el cliente de Binance primero para obtener datos
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

# Gestión del título dinámico y emoji según tendencia del precio
if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

emoji_web = "🟢" if precio_actual >= st.session_state.precio_anterior else "🔴"
st.session_state.precio_anterior = precio_actual

st.set_page_config(
    page_title=f"{emoji_web} ${precio_actual:,.0f} | Terminal de Trading",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. INICIALIZACIÓN DE ESTADOS DE SESIÓN (PERSISTENCIA)
# ==============================================================================
# Memoria para el seguimiento del precio máximo (Trailing Stop)
if 'max_price' not in st.session_state: 
    st.session_state.max_price = 0.0

# Seguimiento del último reporte de actividad (Heartbeat)
if 'ultima_alerta_vida' not in st.session_state: 
    st.session_state.ultima_alerta_vida = datetime.now()

# Registro del último estado de señal enviado para evitar spam en Telegram
if 'estado_actual' not in st.session_state: 
    st.session_state.estado_actual = "NEUTRAL"

# Diseño CSS personalizado para el modo oscuro
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    div[data-testid="stMetricValue"] { color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

st.title(f"🤖 Terminal de Control Pro - BTC: `${precio_actual:,.2f}`")

# ==============================================================================
# 3. PANEL LATERAL (SIDEBAR): FINANZAS Y CONFIGURACIÓN
# ==============================================================================
with st.sidebar:
    st.header("💰 Estado Financiero")
    
    # Intentamos obtener balance y capturar errores de API
    acc_data = client.get_account_status()
    
    if acc_data.get('error'):
        st.error(f"🚨 Error de Conexión: {acc_data['error']}")
        st.metric("Balance Equity", "0.00 USDT", delta="OFFLINE")
    else:
        st.metric(
            "Balance Equity", 
            f"{acc_data['equity']:,.2f} USDT", 
            delta=f"{acc_data['unrealized_pnl']:,.2f} PNL"
        )
        st.success(f"🔗 Conectado: {'DEMO' if client.is_testnet else 'REAL'}")

    st.divider()
    
    # --- DIAGNÓSTICO DE SEÑALES ---
    st.header("📡 Sensores de Mercado")
    
    # Cálculo del contador de reporte de vida (1 hora)
    t_restante = timedelta(hours=1) - (datetime.now() - st.session_state.ultima_alerta_vida)
    minutos_faltantes = int(max(0, t_restante.total_seconds() / 60))
    st.info(f"⌛ Reporte de vida en: **{minutos_faltantes} min**")
    
    # Lógica de Semáforo de Trading (RSI + EMA 20)
    distancia_ema = abs(precio_actual - ema)
    estado_senal = "NEUTRAL"

    if 35 < rsi < 55:
        st.write(f"🟡 **Estado: Neutral ({rsi:.2f})**")
        st.write(f"Distancia a la EMA: `${distancia_ema:,.2f}`")
    elif rsi <= 35:
        if precio_actual > ema:
            estado_senal = "OPORTUNIDAD_LONG"
            st.success("🎯 **¡OPORTUNIDAD LONG!**")
            st.write(f"Precio sobre EMA por `${distancia_ema:,.2f}`")
        else:
            estado_senal = "FILTRO_LONG"
            st.warning("🔴 **Filtro EMA (Debajo)**")
            st.write(f"Esperando cruce alcista... Dist: `${distancia_ema:,.2f}`")
    elif rsi >= 55:
        if precio_actual < ema:
            estado_senal = "OPORTUNIDAD_SHORT"
            st.success("🎯 **¡OPORTUNIDAD SHORT!**")
            st.write(f"Precio bajo EMA por `${distancia_ema:,.2f}`")
        else:
            estado_senal = "FILTRO_SHORT"
            st.warning("🔴 **Filtro EMA (Arriba)**")
            st.write(f"Esperando cruce bajista... Dist: `${distancia_ema:,.2f}`")

    # Si la señal cambió, notificamos por Telegram
    if estado_senal != st.session_state.estado_actual:
        client.enviar_telegram(f"📢 *Cambio de Señal:* {estado_senal}\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`")
        st.session_state.estado_actual = estado_senal

    st.divider()
    
    # --- AJUSTES DE RIESGO ---
    st.header("⚙️ Gestión de Riesgo")
    monto_riesgo = st.number_input("Inversión USDT", value=50.0, step=10.0)
    apalancamiento = st.slider("Apalancamiento (X)", 1, 125, 20)
    
    st.subheader("🛡️ Salidas")
    take_profit_manual = st.number_input("TP (Precio Fijo)", value=0.0)
    stop_loss_manual = st.number_input("SL (Precio Fijo)", value=0.0)
    
    auto_trading = st.toggle("🚀 OPERACIÓN AUTOMÁTICA", value=True)

# ==============================================================================
# 4. CUERPO PRINCIPAL: GRÁFICO PROFESIONAL
# ==============================================================================
[Image of a cryptocurrency technical analysis chart with RSI and EMA indicators showing entry and exit zones]

components.html(f"""
    <div style="height:480px;">
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15",
          "theme": "dark", "style": "1", "locale": "es", "toolbar_bg": "#f1f3f6",
          "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": true,
          "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]
        }});
        </script>
        <div id="tv_chart"></div>
    </div>
    """, height=480)

# ==============================================================================
# 5. GESTIÓN DE POSICIONES ACTIVAS (PNL Y ROI)
# ==============================================================================
posicion_actual = client.get_open_positions()

if posicion_actual:
    lado_pos = "LONG" if float(posicion_actual['positionAmt']) > 0 else "SHORT"
    precio_entrada = float(posicion_actual['entryPrice'])
    tamano_pos = abs(float(posicion_actual['positionAmt']))
    
    # Cálculo de PNL y ROI Real
    if lado_pos == "LONG":
        pnl_no_realizado = (precio_actual - precio_entrada) * tamano_pos
    else:
        pnl_no_realizado = (precio_entrada - precio_actual) * tamano_pos
        
    roi_porcentual = (pnl_no_realizado / (precio_entrada * tamano_pos / apalancamiento)) * 100 if precio_entrada > 0 else 0
    indicador_color = "🟢" if pnl_no_realizado >= 0 else "🔴"
    
    st.warning(f"⚠️ **POSICIÓN {lado_pos} EN CURSO**")
    m1, m2, m3 = st.columns(3)
    m1.metric("Entrada", f"${precio_entrada:,.2f}")
    m2.metric("PNL USDT", f"{indicador_color} {pnl_no_realizado:.2f}")
    m3.metric("ROI", f"{roi_porcentual:.2f}%")

    # Botón de cierre inmediato
    if st.button("⛔ CERRAR POSICIÓN TOTAL", use_container_width=True):
        client.place_order("BTCUSDT", "SELL" if lado_pos == "LONG" else "BUY", str(tamano_pos))
        client.registrar_trade(lado_pos, precio_entrada, precio_actual, pnl_no_realizado)
        st.rerun()

    # Lógica de cierre por TP/SL manual del Sidebar
    if (lado_pos == "LONG" and ((take_profit_manual > 0 and precio_actual >= take_profit_manual) or (stop_loss_manual > 0 and precio_actual <= stop_loss_manual))) or \
       (lado_pos == "SHORT" and ((take_profit_manual > 0 and precio_actual <= take_profit_manual) or (stop_loss_manual > 0 and precio_actual >= stop_loss_manual))):
        client.place_order("BTCUSDT", "SELL" if lado_pos == "LONG" else "BUY", str(tamano_pos))
        client.registrar_trade(lado_pos, precio_entrada, precio_actual, pnl_no_realizado)
        client.enviar_telegram(f"🎯 *CIERRE POR LÍMITE:* PNL `{pnl_no_realizado:.2f} USDT`")
        st.rerun()
else:
    # --- CONTROLES MANUALES (SÓLO SI NO HAY POSICIÓN) ---
    st.info("🔎 **Sin posiciones detectadas.** Operar manualmente:")
    c_manual1, c_manual2 = st.columns(2)
    qty_calculada = round((monto_riesgo * apalancamiento) / precio_actual, 3) if precio_actual > 0 else 0
    
    if c_manual1.button("🟢 COMPRAR (LONG) MANUAL", use_container_width=True):
        res = client.place_order("BTCUSDT", "BUY", str(qty_calculada))
        if res: st.success("Orden enviada"); st.rerun()
    
    if c_manual2.button("🔴 VENDER (SHORT) MANUAL", use_container_width=True):
        res = client.place_order("BTCUSDT", "SELL", str(qty_calculada))
        if res: st.success("Orden enviada"); st.rerun()

# ==============================================================================
# 6. HISTORIAL DE TRADES (POSTGRESQL)
# ==============================================================================
st.divider()
st.subheader("📋 Historial Reciente de Operaciones")
df_historial = client.obtener_historial_db()

if df_historial is not None and not df_historial.empty:
    st.table(df_historial)
else:
    st.write("Conectando con PostgreSQL para cargar el historial...")

# ==============================================================================
# 7. HEARTBEAT Y CICLO DE REFRESCO
# ==============================================================================
# Si pasa una hora, enviamos reporte de vida a Telegram
if (datetime.now() - st.session_state.ultima_alerta_vida) > timedelta(hours=1):
    client.enviar_telegram(f"💓 *CENTINELA:* BTC `${precio_actual:,.2f}` | RSI `{rsi:.2f}`")
    st.session_state.ultima_alerta_vida = datetime.now()

# Refresco automático cada 10 segundos para no saturar la API
time.sleep(10)
st.rer
