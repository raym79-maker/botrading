import streamlit as st
import time, os
import streamlit.components.v1 as components
from binance_client import BinanceClient

st.set_page_config(page_title="Terminal Full Auto 2026", layout="wide")
client = BinanceClient()

if 'max_price' not in st.session_state: st.session_state.max_price = 0.0

st.title("🤖 Terminal de Trading - MODO FULL AUTO")

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("💰 Estado")
    info = client.get_account_status()
    st.metric("Equity", f"{info['equity']:,.2f} USDT", delta=f"{info['unrealized_pnl']:,.2f} PNL")
    
    st.divider()
    st.header("⚙️ Configuración")
    cantidad = st.number_input("CANTIDAD BTC", value=0.002, format="%.3f")
    
    # ACTIVADOS POR DEFECTO
    use_trailing = st.checkbox("Activar Trailing Stop", value=True)
    distancia_ts = st.number_input("Distancia Trailing (USDT)", value=150.0)
    auto_mode = st.toggle("🚀 ESTRATEGIA AUTO (RSI+EMA)", value=True)
    
    rsi, ema, precio_actual = client.get_indicators()
    st.metric("BTC Precio Actual", f"{precio_actual:,.2f} USDT")

# --- GRÁFICO XL ---
components.html(f"""<div style="height:600px;"><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{"autosize": true, "symbol": "BINANCE:BTCUSDT", "interval": "15", "theme": "dark", "container_id": "tv_chart", "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"]}});</script><div id="tv_chart"></div></div>""", height=600)

# --- LÓGICA DE POSICIÓN ---
posicion = client.get_open_positions("BTCUSDT")
pnl_valor = 0.0

if posicion:
    side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
    entry_p = float(posicion['entryPrice'])
    tamano = abs(float(posicion['positionAmt']))
    
    if precio_actual > 0:
        pnl_valor = (precio_actual - entry_p) * tamano if side == "LONG" else (entry_p - precio_actual) * tamano
        
        # Trailing Stop Dinámico
        if use_trailing:
            if st.session_state.max_price == 0: st.session_state.max_price = precio_actual
            if side == "LONG":
                if precio_actual > st.session_state.max_price: st.session_state.max_price = precio_actual
                if precio_actual <= (st.session_state.max_price - distancia_ts):
                    client.place_order("BTCUSDT", "SELL", str(tamano))
                    client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
                    client.enviar_telegram(f"📉 *CIERRE TRAILING (LONG)*\nPNL: `{pnl_valor:.2f} USDT`\nPrecio: `{precio_actual}`")
                    st.session_state.max_price = 0 ; st.rerun()
            else:
                if st.session_state.max_price == 0 or precio_actual < st.session_state.max_price: st.session_state.max_price = precio_actual
                if precio_actual >= (st.session_state.max_price + distancia_ts):
                    client.place_order("BTCUSDT", "BUY", str(tamano))
                    client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
                    client.enviar_telegram(f"📈 *CIERRE TRAILING (SHORT)*\nPNL: `{pnl_valor:.2f} USDT`\nPrecio: `{precio_actual}`")
                    st.session_state.max_price = 0 ; st.rerun()

        st.warning(f"**POSICIÓN ACTIVA: {side}** | Entrada: **{entry_p:,.2f}** | PNL: {pnl_valor:,.4f}")

else:
    st.session_state.max_price = 0
    if auto_mode and precio_actual > 0 and rsi > 0:
        if rsi < 35 and precio_actual > ema:
            client.place_order("BTCUSDT", "BUY", str(cantidad))
            client.enviar_telegram(f"🚀 *NUEVA POSICIÓN (LONG)*\nPrecio: `{precio_actual}`\nRSI: `{rsi}`")
            st.rerun()
        elif rsi > 65 and precio_actual < ema:
            client.place_order("BTCUSDT", "SELL", str(cantidad))
            client.enviar_telegram(f"📉 *NUEVA POSICIÓN (SHORT)*\nPrecio: `{precio_actual}`\nRSI: `{rsi}`")
            st.rerun()

# --- BOTONES ---
st.divider()
if st.button("⛔ CERRAR POSICIÓN MANUAL"):
    if posicion:
        client.place_order("BTCUSDT", "SELL" if side == "LONG" else "BUY", str(tamano))
        client.registrar_trade(side, entry_p, precio_actual, pnl_valor)
        client.enviar_telegram(f"⛔ *CIERRE MANUAL*\nPNL: `{pnl_valor:.2f} USDT`")
        st.rerun()

st.subheader("📋 Historial (PostgreSQL)")
df = client.obtener_historial_db()
if df is not None: st.table(df)

time.sleep(2); st.rerun()
