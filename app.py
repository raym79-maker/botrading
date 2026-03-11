import streamlit as st
import time, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from binance_client import BinanceClient

# 1. SETUP INICIAL
client = BinanceClient()
rsi, ema, precio_actual = client.get_indicators()

if 'precio_anterior' not in st.session_state:
    st.session_state.precio_anterior = precio_actual

emoji_p = "🟢" if precio_actual >= st.session_state.precio_anterior else "🔴"
st.session_state.precio_anterior = precio_actual

st.set_page_config(
    page_title=f"{emoji_p} ${precio_actual:,.0f} | Terminal Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'estado_actual' not in st.session_state: st.session_state.estado_actual = "NEUTRAL"
if 'ultima_alerta' not in st.session_state: st.session_state.ultima_alerta = datetime.now()

st.title(f"🤖 Terminal Pro BTC - `${precio_actual:,.2f}`")

# --- 2. SIDEBAR (BALANCE Y RIESGO) ---
with st.sidebar:
    st.header("💰 Estado de Cuenta")
    acc = client.get_account_status()
    if acc['error']:
        st.error(f"🚨 {acc['error']}")
        st.info("💡 Ve a Variables en Railway y pega BINANCE_API_SECRET.")
    else:
        st.metric("Balance Equity", f"{acc['equity']:,.2f} USDT", delta=f"{acc['unrealized_pnl']:,.2f} PNL")
        st.success(f"Modo: {'DEMO' if client.is_testnet else 'REAL'}")

    st.divider()
    st.header("📡 Diagnóstico de Señal")
    dist_ema = abs(precio_actual - ema)
    if 35 < rsi < 55:
        st.write(f"🟡 RSI Neutral ({rsi:.2f})")
    elif rsi <= 35:
        if precio_actual > ema:
            st.success("🎯 OPORTUNIDAD LONG")
        else:
            st.warning("🔴 Filtro: Bajo la EMA")
    elif rsi >= 55:
        if precio_actual < ema:
            st.success("🎯 OPORTUNIDAD SHORT")
        else:
            st.warning("🔴 Filtro: Sobre la EMA")

    st.divider()
    st.header("⚙️ Ajustes de Riesgo")
    riesgo = st.number_input("Inversión USDT", value=50.0, step=10.0)
    lev = st.slider("Apalancamiento", 1, 125, 20)
    auto = st.toggle("🚀 Trading Automático", value=True)

# --- 3. GRÁFICO TRADINGVIEW ---
components.html(f"""
    <div style="height:480px;">
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark",
          "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]
        }});
        </script><div id="tv_chart"></div>
    </div>
    """, height=480)

# --- 4. GESTIÓN DE POSICIÓN ---
pos = client.get_open_positions()

if pos:
    lado = "LONG" if float(pos['positionAmt']) > 0 else "SHORT"
    ent = float(pos['entryPrice'])
    tam = abs(float(pos['positionAmt']))
    pnl = (precio_actual - ent) * tam if lado == "LONG" else (ent - precio_actual) * tam
    roi = (pnl / (ent * tam / lev)) * 100 if ent > 0 else 0
    
    st.warning(f"⚠️ POSICIÓN {lado} ACTIVA")
    c1, c2, c3 = st.columns(3)
    c1.metric("Precio Entrada", f"${ent:,.2f}")
    c2.metric("PNL Actual", f"{pnl:.2f} USDT")
    c3.metric("ROI Real", f"{roi:.2f}%")
    
    if st.button("⛔ CERRAR POSICIÓN AHORA", use_container_width=True):
        client.place_order("BTCUSDT", "SELL" if lado == "LONG" else "BUY", str(tam))
        client.registrar_trade(lado, ent, precio_actual, pnl)
        st.rerun()
else:
    st.info("🔎 No hay posiciones abiertas. Operar manualmente:")
    cm1, cm2 = st.columns(2)
    qty = round((riesgo * lev) / precio_actual, 3) if precio_actual > 0 else 0
    
    if cm1.button("🟢 ABRIR LONG MANUAL", use_container_width=True):
        if qty > 0:
            client.place_order("BTCUSDT", "BUY", qty)
            st.rerun()
    
    if cm2.button("🔴 ABRIR SHORT MANUAL", use_container_width=True):
        if qty > 0:
            client.place_order("BTCUSDT", "SELL", qty)
            st.rerun()

# --- 5. HISTORIAL DE TRADES ---
st.divider()
st.subheader("📋 Historial de PostgreSQL")
df_h = client.obtener_historial_db()
if df_h is not None and not df_h.empty:
    st.table(df_h)
else:
    st.write("Esperando registros en la base de datos...")

# Refresco automático cada 10 segundos
time.sleep(10)
st.rerun()
