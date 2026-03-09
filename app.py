import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# 1. CONFIGURACIÓN DE PÁGINA E INDICADORES
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

# Guardar precio anterior para la flecha de la pestaña
if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

emoji_tendencia = "🟢" if precio_actual > st.session_state.precio_anterior else "🔴"
st.session_state.precio_anterior = precio_actual

st.set_page_config(
    page_title=f"{emoji_tendencia} ${precio_actual:,.0f} | Bot Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. INICIALIZACIÓN DE ESTADOS DE SESIÓN (Memoria del Bot)
if 'max_price' not in st.session_state: st.session_state.max_price = 0.0
if 'ultima_alerta_vida' not in st.session_state: st.session_state.ultima_alerta_vida = datetime.now()
if 'estado_actual' not in st.session_state: st.session_state.estado_actual = "NEUTRAL"

st.title(f"🤖 Terminal de Trading Pro - BTC: ${precio_actual:,.2f}")

# --- 3. PANEL LATERAL (DIAGNÓSTICO Y CONFIGURACIÓN) ---
with st.sidebar:
    st.header("💰 Estado de Cuenta")
    acc_info = client.get_account_status()
    st.metric("Balance Total", f"{acc_info['equity']:,.2f} USDT", delta=f"{acc_info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("📡 Diagnóstico en Tiempo Real")
    
    # Contador para el Reporte de Vida (Heartbeat) de 1 Hora
    t_restante = timedelta(hours=1) - (datetime.now() - st.session_state.ultima_alerta_vida)
    mins_faltantes = int(max(0, t_restante.total_seconds() / 60))
    st.info(f"⌛ Próximo reporte de vida en: **{mins_faltantes} min**")
    
    # Lógica de Diagnóstico con Distancia a la EMA
    dist_ema = abs(precio_actual - ema)
    nuevo_estado = "NEUTRAL"
    msg_telegram = ""

    if 35 < rsi < 55:
        nuevo_estado = "NEUTRAL"
        st.write(f"🟡 **Estado Neutral ({rsi:.2f})**: Esperando niveles de entrada. Distancia EMA: `${dist_ema:.2f}`")
    elif rsi <= 35:
        if precio_actual > ema:
            nuevo_estado = "OPORTUNIDAD_LONG"
            msg_telegram = f"🎯 **Oportunidad LONG**: RSI ({rsi:.2f}) en compra y sobre la EMA. Precio: `${precio_actual:,.2f}`"
            st.success(f"🎯 **Oportunidad LONG**: Precio sobre la EMA por `${dist_ema:.2f}`")
        else:
            nuevo_estado = "FILTRO_LONG"
            msg_telegram = f"🔴 **Filtro EMA (LONG)**: RSI listo, pero precio `${precio_actual:,.2f}` está `${dist_ema:.2f}` bajo la EMA."
            st.warning(f"🔴 **Filtro EMA**: Esperando cruce al alza. Distancia: `${dist_ema:.2f}`")
    elif rsi >= 55:
        if precio_actual < ema:
            nuevo_estado = "OPORTUNIDAD_SHORT"
            msg_telegram = f"🎯 **Oportunidad SHORT**: RSI ({rsi:.2f}) en venta y bajo la EMA. Precio: `${precio_actual:,.2f}`"
            st.success(f"🎯 **Oportunidad SHORT**: Precio bajo la EMA por `${dist_ema:.2f}`")
        else:
            nuevo_estado = "FILTRO_SHORT"
            msg_telegram = f"🔴 **Filtro EMA (SHORT)**: RSI listo, pero precio `${precio_actual:,.2f}` está `${dist_ema:.2f}` sobre la EMA."
            st.warning(f"🔴 **Filtro EMA**: Esperando cruce a la baja. Distancia: `${dist_ema:.2f}`")

    # Enviar a Telegram solo si cambia el estado
    if nuevo_estado != st.session_state.estado_actual and msg_telegram != "":
        client.enviar_telegram(msg_telegram)
        st.session_state.estado_actual = nuevo_estado

    st.divider()
    st.header("⚙️ Configuración de Riesgo")
    usdt_riesgo = st.number_input("Inversión por operación (USDT)", value=50.0, step=10.0)
    lev = st.slider("Apalancamiento (Leverage)", 1, 125, 20)
    
    st.subheader("🛡️ Protecciones")
    tp_input = st.number_input("Take Profit (Precio fijo)", value=0.0)
    sl_input = st.number_input("Stop Loss (Precio fijo)", value=0.0)
    use_trailing = st.checkbox("Trailing Stop Activo", value=True)
    distancia_ts = st.number_input("Distancia Trailing (USDT)", value=500.0)
    
    auto_mode = st.toggle("🚀 MODO AUTO (Bot Operando)", value=True)

# --- 4. CUERPO PRINCIPAL (GRÁFICO Y POSICIÓN) ---

# Widget de TradingView
components.html(f"""
    <div style="height:450px;">
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
    """, height=450)

# Monitoreo de Posición Activa
posicion = client.get_open_positions("BTCUSDT")

if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry_p = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    # Cálculo de PNL y ROI
    pnl_val = (precio_actual - entry_p) * tamano if side == "LONG" else (entry_p - precio_actual) * tamano
    roi_pct = (pnl_val / (entry_p * tamano / lev)) * 100
    
    # Indicador visual de PNL
    pnl_color = "🟢" if pnl_val >= 0 else "🔴"
    
    st.warning(f"⚠️ **POSICIÓN EN CURSO: {side}**")
    c1, c2, c3 = st.columns(3)
    c1.metric("Precio Entrada", f"${entry_p:,.2f}")
    c2.metric("PNL Actual", f"{pnl_color} {pnl_val:,.2f} USDT")
    c3.metric("ROI %", f"{roi_pct:.2f}%")

    # --- LÓGICA DE CIERRES ---
    
    # 1. Cierre por Take Profit o Stop Loss Manual (Inputs)
    if side == "LONG":
        if (tp_input > 0 and precio_actual >= tp_input) or (sl_input > 0 and precio_actual <= sl_input):
            client.place_order("BTCUSDT", "SELL", str(tamano))
            client.registrar_trade(side, entry_p, precio_actual, pnl_val)
            client.enviar_telegram(f"🎯 *CIERRE POR LÍMITE (LONG)*\nPNL: `{pnl_val:.2f} USDT`")
            st.rerun()
    else: # SHORT
        if (tp_input > 0 and precio_actual <= tp_input) or (sl_input > 0 and precio_actual >= sl_input):
            client.place_order("BTCUSDT", "BUY", str(tamano))
            client.registrar_trade(side, entry_p, precio_actual, pnl_val)
            client.enviar_telegram(f"🎯 *CIERRE POR LÍMITE (SHORT)*\nPNL: `{pnl_val:.2f} USDT`")
            st.rerun()

    # 2. Lógica de Trailing Stop
    if use_trailing:
        if st.session_state.max_price == 0: st.session_state.max_price = precio_actual
        
        if side == "LONG":
            if precio_actual > st.session_state.max_price: st.session_state.max_price = precio_actual
            if precio_actual <= (st.session_state.max_price - distancia_ts):
                client.place_order("BTCUSDT", "SELL", str(tamano))
                client.registrar_trade(side, entry_p, precio_actual, pnl_val)
                client.enviar_telegram(f"🛡️ *TRAILING STOP ACTIVADO (LONG)*\nCierre en: `${precio_actual:,.2f}`\nPNL: `{pnl_val:.2f} USDT`")
                st.session_state.max_price = 0 ; st.rerun()
        else: # SHORT
            if st.session_state.max_price == 0 or precio_actual < st.session_state.max_price: st.session_state.max_price = precio_actual
            if precio_actual >= (st.session_state.max_price + distancia_ts):
                client.place_order("BTCUSDT", "BUY", str(tamano))
                client.registrar_trade(side, entry_p, precio_actual, pnl_val)
                client.enviar_telegram(f"🛡️ *TRAILING STOP ACTIVADO (SHORT)*\nCierre en: `${precio_actual:,.2f}`\nPNL: `{pnl_val:.2f} USDT`")
                st.session_state.max_price = 0 ; st.rerun()

else:
    # --- LÓGICA DE APERTURA AUTOMÁTICA ---
    st.session_state.max_price = 0
    if auto_mode and precio_actual > 0:
        # Calcular tamaño basado en el margen y apalancamiento
        cant_op = round((usdt_riesgo * lev) / precio_actual, 3)
        
        if rsi <= 35 and precio_actual > ema:
            client.place_order("BTCUSDT", "BUY", str(cant_op))
            client.enviar_telegram(f"🚀 *NUEVA POSICIÓN: LONG*\nPrecio: `${precio_actual:,.2f}`\nMargen: `{usdt_riesgo} USDT` x{lev}")
            st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()
            
        elif rsi >= 55 and precio_actual < ema:
            client.place_order("BTCUSDT", "SELL", str(cant_op))
            client.enviar_telegram(f"📉 *NUEVA POSICIÓN: SHORT*\nPrecio: `${precio_actual:,.2f}`\nMargen: `{usdt_riesgo} USDT` x{lev}")
            st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()

# --- 5. HEARTBEAT (CENTINELA) ---
if (datetime.now() - st.session_state.ultima_alerta_vida) > timedelta(hours=1):
    client.enviar_telegram(f"💓 *REPORTE DE ACTIVIDAD*\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`\nEstado: `{st.session_state.estado_actual}`")
    st.session_state.ultima_alerta_vida = datetime.now()

# --- 6. CONTROLES MANUALES ---
st.divider()
st.subheader("🕹️ Operación Manual")
col1, col2, col3 = st.columns(3)
manual_qty = round((usdt_riesgo * lev) / precio_actual, 3) if precio_actual > 0 else 0

if col1.button("🟢 COMPRAR (LONG) MANUAL", use_container_width=True):
    client.place_order("BTCUSDT", "BUY", str(manual_qty))
    client.enviar_telegram("🚀 *ENTRADA MANUAL: LONG*")
    st.rerun()

if col2.button("🔴 VENDER (SHORT) MANUAL", use_container_width=True):
    client.place_order("BTCUSDT", "SELL", str(manual_qty))
    client.enviar_telegram("📉 *ENTRADA MANUAL: SHORT*")
    st.rerun()

if col3.button("⛔ CERRAR TODO AHORA", use_container_width=True):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry_p, precio_actual, pnl_val if 'pnl_val' in locals() else 0)
        client.enviar_telegram("⛔ *ORDEN DE CIERRE MANUAL EJECUTADA*")
        st.rerun()

# --- 7. HISTORIAL DE POSTGRESQL ---
st.divider()
st.subheader("📋 Historial Reciente (PostgreSQL)")
df_trades = client.obtener_historial_db()
if df_trades is not None and not df_trades.empty:
    st.table(df_trades)
else:
    st.info("No hay operaciones registradas en el historial todavía.")

# Bucle de refresco
time.sleep(2)
st.rerun()
