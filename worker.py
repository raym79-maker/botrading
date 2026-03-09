import time, os
from datetime import datetime, timedelta
from binance_client import BinanceClient

def bot_permanente():
    client = BinanceClient()
    estado_previo = "NEUTRAL"
    ultima_alerta = datetime.now()
    print("🚀 Worker iniciado. Vigilando el mercado 24/7...")

    while True:
        try:
            rsi, ema, precio = client.get_indicators()
            pos = client.get_open_positions()
            
            # Lógica de decisiones
            estado = "NEUTRAL"
            if rsi <= 35:
                estado = "OPORTUNIDAD_LONG" if precio > ema else "FILTRO_LONG"
            elif rsi >= 55:
                estado = "OPORTUNIDAD_SHORT" if precio < ema else "FILTRO_SHORT"

            # 1. Alerta de cambio de estado a Telegram
            if estado != estado_previo:
                client.enviar_telegram(f"📢 *ESTADO*: {estado}\nPrecio: `${precio:,.2f}` | RSI: `{rsi:.2f}`")
                estado_previo = estado

            # 2. Operación Automática (Margen Fijo 50 USDT x20)
            if not pos:
                cantidad = round((50.0 * 20) / precio, 3) 
                if estado == "OPORTUNIDAD_LONG":
                    client.place_order("BTCUSDT", "BUY", str(cantidad))
                    client.enviar_telegram("🚀 *LONG AUTOMÁTICO EJECUTADO*")
                    ultima_alerta = datetime.now()
                elif estado == "OPORTUNIDAD_SHORT":
                    client.place_order("BTCUSDT", "SELL", str(cantidad))
                    client.enviar_telegram("📉 *SHORT AUTOMÁTICO EJECUTADO*")
                    ultima_alerta = datetime.now()

            # 3. Reporte de Vida cada 1 hora
            if (datetime.now() - ultima_alerta) > timedelta(hours=1):
                client.enviar_telegram(f"💓 *CENTINELA ACTIVO*\nBTC: `${precio:,.2f}` | RSI: `{rsi:.2f}`")
                ultima_alerta = datetime.now()

        except Exception as e:
            print(f"Error en el ciclo del bot: {e}")
        
        # Espera 15 segundos entre revisiones
        time.sleep(15)

if __name__ == "__main__":
    bot_permanente()
