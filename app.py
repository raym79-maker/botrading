import streamlit as st
import time, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Trading Master 2026", layout="wide")
client = BinanceClient()

st.title("🤖 Terminal Trading (Estrategia Completa)")

# --- PANEL LATERAL (Sidebar) ---
with st.sidebar:
    st.header("💰 Estado de Cuenta")
    info = client.get_account_status()
    st.metric("Equity (Total)", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    # 1. RESTAURADO: Apalancamiento
    st.header("⚖️ Gestión de Riesgo")
    lev = st.slider("Apalancamiento (x)", 1, 125, 20)
    if st.button("Aplicar Apalancamiento"):
        client.set_leverage("BTCUSDT", lev)
        st.success(f"Ajustado a {lev}x")

    st.divider()
    # 2. RESTAURADO: Configuración de Orden (Cantidad, TP, SL)
    st.header("⚙️ Configuración de Orden")
    cantidad = st.number_input("CANTIDAD BTC", value=0.002, format="%.3f")
    tp_input = st.number_input("Take Profit (Precio fijo)", value=0.0)
    sl_input = st.number_input("Stop Loss (Precio fijo)", value=0.0)
    
    st.divider()
    # 3. MANTENIDO: Trailing Stop
    st.header("🛡️ Protecciones Dinámicas")
    use_trailing = st.checkbox("Activar Trailing Stop")
    distancia_ts = st.number_input("Distancia Trailing (USDT)", value=50.0, step=10.0)
    
    st.divider()
    auto_mode = st.toggle("🚀 ACTIVAR ESTRATEGIA AUTO")
    
    # Indicadores en tiempo real
    rsi, ema, precio_actual = client.get_indicators()
    c1, c2 = st.columns(2)
    c1.metric("RSI (14)", f"{rsi if rsi > 0 else 'Cargando'}")
    c2.metric("EMA (20)", f"{ema if ema > 0 else 'Cargando'}")
    st.metric("BTC Precio Actual", f"{precio_actual:,.2f} USDT")

# --- GRÁFICO XL (600px) ---
components.html(f"""
<div style="height:600px;">
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart",
    "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]
  }});
  </script>
  <div id="tv_chart"></div>
</div>
""", height=600)

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")
pnl_valor = 0.0
if 'max_price' not in st.session_state: st.session_state.max_price = 0.0

if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry_p = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    if precio_actual > 0:
        pnl_valor = (precio_actual - entry_p) * tamano if side == "LONG" else (entry_p - precio_actual) * tamano
        
        # Lógica de cierre por TP/SL Fijos
        if (side == "LONG" and ((tp_input > 0 and precio_actual >= tp_input) or (sl_input > 0 and precio_actual <= sl_input))) or \
           (side == "SHORT" and ((tp_input > 0 and precio_actual <= tp_input) or (sl_input > 0 and precio_actual >= sl_input))):
            client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
            client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
            st.rerun()

        # Lógica de Trailing Stop
        if use_trailing:
            if st.session_state.max_price == 0: st.session_state.max_price = precio_actual
            if side == "LONG":
                if precio_actual > st.session_state.max_price: st.session_state.max_price = precio_actual
                dynamic_sl = st.session_state.max_price - distancia_ts
                if precio_actual <= dynamic_sl:
                    client.place_order("BTCUSDT", "SELL", str(tamano))
                    client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
                    st.session_state.max_price = 0 ; st.rerun()
            else:
                if st.session_state.max_price == 0 or precio_actual < st.session_state.max_price: 
                    st.session_state.max_price = precio_actual
                dynamic_sl = st.session_state.max_price + distancia_ts
                if precio_actual >= dynamic_sl:
                    client.place_order("BTCUSDT", "BUY", str(tamano))
                    client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
                    st.session_state.max_price = 0 ; st.rerun()

        st.warning(f"**POSICIÓN ACTIVA: {side}** | Entrada: **{entry_p:,.2f}** | PNL: {'🟢' if pnl_valor >= 0 else '🔴'} {pnl_valor:,.4f} USDT")

elif auto_mode and precio_actual > 0 and rsi > 0:
    if rsi < 35 and precio_actual > ema:
        client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
    elif rsi > 65 and precio_actual < ema:
        client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()

# --- BOTONES ---
st.divider()
c1, c2, c3 = st.columns(3)
if c1.button("🟢 MANUAL LONG"): client.place_order("BTCUSDT", "BUY", str(cantidad)); st.rerun()
if c2.button("🔴 MANUAL SHORT"): client.place_order("BTCUSDT", "SELL", str(cantidad)); st.rerun()
if c3.button("⛔ CERRAR Y REGISTRAR"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
        st.rerun()

# --- HISTORIAL ---
st.subheader("📋 Historial (PostgreSQL)")
df = client.obtener_historial_db()
if df is not None: st.table(df)

time.sleep(2); st.rerun()
