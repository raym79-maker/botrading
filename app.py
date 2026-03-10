import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# 1. INICIALIZACIÓN Y CONFIGURACIÓN DE PÁGINA
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

# Guardar precio anterior para el indicador de tendencia en la pestaña
if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

emoji_tendencia = "🟢" if precio_actual > st.session_state.precio_anterior else "🔴"
st.session_state.precio_anterior = precio_actual

st.set_page_config(
    page_title=f"{emoji_tendencia} ${precio_actual:,.0f} | Pro Bot",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. ESTADOS DE SESIÓN (Memoria persistente)
if 'max_price' not in st.session_state: st.session_state.max_price = 0.0
if 'ultima_alerta_vida' not in st.session_state: st.session_state.ultima_alerta_vida = datetime.now()
if 'estado_actual' not in st.session_state: st.session_state.estado_actual = "NEUTRAL"

st.title(f"🤖 Terminal de Control BTC - Precio Actual: ${precio_actual:,.2f}")

# --- 3. PANEL LATERAL (DIAGNÓSTICO Y AJUSTES) ---
with st.sidebar:
    st.header("💰 Estado de Cuenta")
    acc = client.get_account_status()
    st.metric("Balance Equity", f"{acc['equity']:,.2f} USDT", delta=f"{acc['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("📡 Diagnóstico de Señal")
    
    # Reporte de Vida (Heartbeat) de 1 Hora
    t_restante = timedelta(hours=1) - (datetime.now() - st.session_state.ultima_alerta_vida)
    mins_faltantes = int(max(0, t_restante.total_seconds() / 60))
    st.info(f"⌛ Próximo reporte de vida en: **{mins_faltantes} min**")
    
    dist_ema = abs(precio_actual - ema)
    nuevo_estado = "NEUTRAL"

    # Lógica de Semáforo de Trading
    if 35 < rsi < 55:
        st.write(f"🟡 **Neutral ({rsi:.2f})**. Distancia EMA: `${dist_ema:.2f}`")
    elif rsi <= 35:
        if precio_actual > ema:
            nuevo_estado = "OPORTUNIDAD_LONG"
            st.success(f"🎯 **¡LONG!** Precio sobre EMA por `${dist_ema:.2f}`")
        else:
            nuevo_estado = "FILTRO_LONG"
            st.warning(f"🔴 **Filtro**: RSI bajo pero precio `${dist_ema:.2f}` bajo EMA.")
    elif rsi >= 55:
        if precio_actual < ema:
            nuevo_estado = "OPORTUNIDAD_SHORT"
            st.success(f"🎯 **¡SHORT!** Precio bajo EMA por `${dist_ema:.2f}`")
        else:
            nuevo_estado = "FILTRO_SHORT"
            st.warning(f"🔴 **Filtro**: RSI alto pero precio `${dist_ema:.2f}` sobre EMA.")

    # Notificar cambio de estado a Telegram
    if nuevo_estado != st.session_state.estado_actual:
        client.enviar_telegram(f"📢 Cambio de Estado: *{nuevo_estado}*\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`")
        st.session_state.estado_actual = nuevo_estado

    st.divider()
    st.header("⚙️ Configuración")
    usdt_riesgo = st.number_input("Inversión USDT", value=50.0, step=10.0)
    lev = st.slider("Apalancamiento", 1, 125, 20)
    tp_input = st.number_input("Take Profit (Precio)", value=0.0)
    sl_input = st.number_input("Stop Loss (Precio)", value=0.0)
    
    st.divider()
    st.subheader("🛡️ Protecciones")
    use_trailing = st.checkbox("Trailing Stop Activo", value=True)
    distancia_ts = st.number_input("Distancia Trailing (USDT)", value=500.0)
    auto_mode = st.toggle("🚀 OPERACIÓN AUTOMÁTICA", value=True)

# --- 4. CUERPO PRINCIPAL: GRÁFICO TRADINGVIEW ---
components.html(f"""
    <div style="height:450px;">
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15",
          "theme": "dark", "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]
        }});
        </script>
        <div id="tv_chart"></div>
    </div>
    """, height=450)

# --- 5. GESTIÓN DE POSICIÓN ACTIVA ---
posicion = client.get_open_positions()

if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry_p = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    # Cálculo de PNL y ROI
    pnl = (precio_actual - entry_p) * tamano if side == "LONG" else (entry_p - precio_actual) * tamano
    # ROI = (PNL / Margen) * 100
    roi = (pnl / (entry_p * tamano / lev)) * 100 if entry_p > 0 else 0
    ind = "🟢" if pnl >= 0 else "🔴"
    
    st.warning(f"⚠️ **POSICIÓN {side} EN CURSO**")
    col1, col2, col3 = st.columns(3)
    col1.metric("Precio Entrada", f"${entry_p:,.2f}")
    col2.metric("PNL Actual", f"{ind} {pnl:.2f} USDT")
    col3.metric("ROI %", f"{roi:.2f}%")

    # Lógica de Cierre por TP / SL
    if side == "LONG":
        if (tp_input > 0 and precio_actual >= tp_input) or (sl_input > 0 and precio_actual <= sl_input):
            client.place_order("BTCUSDT", "SELL", str(tamano))
            client.registrar_trade(side, entry_p, precio_actual, pnl)
            client.enviar_telegram(f"🎯 *CIERRE LÍMITE LONG*\nPNL: `{pnl:.2f} USDT` | Precio: `${precio_actual:,.2f}`")
            st.rerun()
    else: # SHORT
        if (tp_input > 0 and precio_actual <= tp_input) or (sl_input > 0 and precio_actual >= sl_input):
            client.place_order("BTCUSDT", "BUY", str(tamano))
            client.registrar_trade(side, entry_p, precio_actual, pnl)
            client.enviar_telegram(f"🎯 *CIERRE LÍMITE SHORT*\nPNL: `{pnl:.2f} USDT` | Precio: `${precio_actual:,.2f}`")
            st.rerun()

    # Lógica de Trailing Stop
    if use_trailing:
        if st.session_state.max_price == 0: st.session_state.max_price = precio_actual
        if side == "LONG":
            if precio_actual > st.session_state.max_price: st.session_state.max_price = precio_actual
            if precio_actual <= (st.session_state.max_price - distancia_ts):
                client.place_order("BTCUSDT", "SELL", str(tamano))
                client.registrar_trade(side, entry_p, precio_actual, pnl)
                client.enviar_telegram(f"🛡️ *TRAILING STOP LONG*\nPNL: `{pnl:.2f} USDT` | Cierre: `${precio_actual:,.2f}`")
                st.session_state.max_price = 0 ; st.rerun()
        else: # SHORT
            if precio_actual < st.session_state.max_price or st.session_state.max_price == 0: st.session_state.max_price = precio_actual
            if precio_actual >= (st.session_state.max_price + distancia_ts):
                client.place_order("BTCUSDT", "BUY", str(tamano))
                client.registrar_trade(side, entry_p, precio_actual, pnl)
                client.enviar_telegram(f"🛡️ *TRAILING STOP SHORT*\nPNL: `{pnl:.2f} USDT` | Cierre: `${precio_actual:,.2f}`")
                st.session_state.max_price = 0 ; st.rerun()
else:
    # Lógica de Apertura Automática (Solo si no hay posición)
    st.session_state.max_price = 0
    if auto_mode and precio_actual > 0:
        cantidad_op = round((usdt_riesgo * lev) / precio_actual, 3)
        if rsi <= 35 and precio_actual > ema:
            client.place_order("BTCUSDT", "BUY", str(cantidad_op))
            client.enviar_telegram(f"🚀 *AUTO LONG EJECUTADO*\nPrecio: `${precio_actual:,.2f}`")
            st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()
        elif rsi >= 55 and precio_actual < ema:
            client.place_order("BTCUSDT", "SELL", str(cantidad_op))
            client.enviar_telegram(f"📉 *AUTO SHORT EJECUTADO*\nPrecio: `${precio_actual:,.2f}`")
            st.session_state.ultima_alerta_vida = datetime.now() ; st.rerun()

# --- CONTROLES MANUALES ---
st.divider()
st.subheader("🕹️ Operativa Manual")
col1, col2, col3 = st.columns(3)

# Calculamos la cantidad (Importante: Redondear a 3 decimales para BTC)
if precio_actual > 0:
    qty_m = round((usdt_riesgo * lev) / precio_actual, 3)
else:
    qty_m = 0

if col1.button("🟢 COMPRAR (LONG)", use_container_width=True):
    if qty_m > 0:
        res = client.place_order("BTCUSDT", "BUY", str(qty_m))
        if res:
            st.success(f"🚀 Orden LONG enviada: {qty_m} BTC")
            client.enviar_telegram(f"🚀 *ORDEN MANUAL:* LONG de `{qty_m} BTC` enviado.")
            st.rerun()
    else:
        st.error("Cantidad inválida. Revisa el precio y el riesgo.")

if col2.button("🔴 VENDER (SHORT)", use_container_width=True):
    if qty_m > 0:
        res = client.place_order("BTCUSDT", "SELL", str(qty_m))
        if res:
            st.success(f"📉 Orden SHORT enviada: {qty_m} BTC")
            client.enviar_telegram(f"📉 *ORDEN MANUAL:* SHORT de `{qty_m} BTC` enviado.")
            st.rerun()

# --- 7. HEARTBEAT Y HISTORIAL ---
if (datetime.now() - st.session_state.ultima_alerta_vida) > timedelta(hours=1):
    client.enviar_telegram(f"💓 *CENTINELA ACTIVO*\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`\nEstado: `{st.session_state.estado_actual}`")
    st.session_state.ultima_alerta_vida = datetime.now()

st.divider()
st.subheader("📋 Historial de Trades (PostgreSQL)")
df_trades = client.obtener_historial_db()
if df_trades is not None and not df_trades.empty:
    st.table(df_trades)
else:
    st.info("Buscando registros en la base de datos...")

# Bucle de refresco automático cada 5 segundos
time.sleep(5)
st.rerun()
