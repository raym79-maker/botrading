import streamlit as st
import time, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Trading Pro 2026", layout="wide")
client = BinanceClient()

st.title("🤖 Terminal Trading (RSI+EMA + Trailing Stop)")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("💰 Cuenta")
    info = client.get_account_status()
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("⚙️ Configuración")
    cantidad = st.number_input("CANTIDAD BTC", value=0.002, format="%.3f")
    
    # NUEVO: Configuración del Trailing Stop
    st.subheader("🛡️ Protecciones")
    use_trailing = st.checkbox("Activar Trailing Stop")
    distancia_ts = st.number_input("Distancia Trailing (USDT)", value=50.0, step=10.0, help="Distancia que el SL mantendrá respecto al precio máximo alcanzado.")
    
    st.divider()
    auto_mode = st.toggle("🚀 MODO ESTRATEGIA AUTO")
    
    rsi, ema, precio_actual = client.get_indicators()
    c1, c2 = st.columns(2)
    c1.metric("RSI (14)", f"{rsi if rsi > 0 else 'Cargando...'}")
    c2.metric("EMA (20)", f"{ema if ema > 0 else 'Cargando...'}")
    st.metric("BTC Precio Actual", f"{precio_actual:,.2f} USDT")

# --- GRÁFICO XL ---
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

# Usamos st.session_state para recordar el "Mejor Precio" alcanzado durante la operación
if 'max_price' not in st.session_state: st.session_state.max_price = 0.0

if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry_p = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    if precio_actual > 0:
        pnl_valor = (precio_actual - entry_p) * tamano if side == "LONG" else (entry_p - precio_actual) * tamano
        
        # --- MOTOR DE TRAILING STOP ---
        if use_trailing:
            # Inicializar max_price al entrar
            if st.session_state.max_price == 0: st.session_state.max_price = precio_actual
            
            if side == "LONG":
                # Si el precio sube, actualizamos el máximo
                if precio_actual > st.session_state.max_price: st.session_state.max_price = precio_actual
                
                # Cálculo de Stop Loss Dinámico: $$SL = Price_{max} - Distancia$$
                dynamic_sl = st.session_state.max_price - distancia_ts
                st.info(f"🛡️ Trailing SL (LONG): {dynamic_sl:,.2f} (Distancia: {distancia_ts})")
                
                if precio_actual <= dynamic_sl:
                    client.place_order("BTCUSDT", "SELL", str(tamano))
                    client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
                    st.session_state.max_price = 0
                    st.rerun()
            
            else: # Lógica para SHORT
                # Si el precio baja, actualizamos el mínimo
                if st.session_state.max_price == 0 or precio_actual < st.session_state.max_price: 
                    st.session_state.max_price = precio_actual
                
                # Cálculo de Stop Loss Dinámico: $$SL = Price_{min} + Distancia$$
                dynamic_sl = st.session_state.max_price + distancia_ts
                st.info(f"🛡️ Trailing SL (SHORT): {dynamic_sl:,.2f} (Distancia: {distancia_ts})")
                
                if precio_actual >= dynamic_sl:
                    client.place_order("BTCUSDT", "BUY", str(tamano))
                    client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
                    st.session_state.max_price = 0
                    st.rerun()

        st.warning(f"**POSICIÓN ACTIVA: {side}** | Entrada: **{entry_p:,.2f}** | PNL: {'🟢' if pnl_valor >= 0 else '🔴'} {pnl_valor:,.4f} USDT")

else:
    st.session_state.max_price = 0 # Resetear cuando no hay posición
    # Lógica de entrada automática (RSI+EMA)
    if auto_mode and precio_actual > 0 and rsi > 0:
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
st.subheader("📋 Historial Permanente (PostgreSQL)")
df = client.obtener_historial_db()
if df is not None: st.table(df)

time.sleep(2); st.rerun()
