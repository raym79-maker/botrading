import time, os
from datetime import datetime, timedelta
from binance_client import BinanceClient

def ejecutar_bot():
    client = BinanceClient()
    estado_actual = "NEUTRAL"
    ultima_alerta_vida = datetime.now()
    print("🚀 Worker iniciado. Vigilando el mercado 24/7...")

    while True:
        try:
            rsi, ema, precio_actual = client.get_indicators()
            posicion = client.get_open_positions()
            
            # Lógica de estados
            nuevo_estado = "NEUTRAL"
            if rsi <= 35:
                nuevo_estado = "OPORTUNIDAD_LONG" if precio_actual > ema else "FILTRO_LONG"
            elif rsi >= 55:
                nuevo_estado = "OPORTUNIDAD_SHORT" if precio_actual < ema else "FILTRO_SHORT"

            # 1. Alerta de cambio de estado
            if nuevo_estado != estado_actual:
                client.enviar_telegram(f"📢 *ESTADO*: {nuevo_estado}\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`")
                estado_actual = nuevo_estado

            # 2. Apertura Automática (Solo si no hay posición abierta)
            if not posicion:
                # Ajusta aquí tu riesgo fijo
                cantidad = round((50.0 * 20) / precio_actual, 3) 
                
                if nuevo_estado == "OPORTUNIDAD_LONG":
                    client.place_order("BTCUSDT", "BUY", str(cantidad))
                    client.enviar_telegram("🚀 *LONG EJECUTADO AUTOMÁTICAMENTE*")
                elif nuevo_estado == "OPORTUNIDAD_SHORT":
                    client.place_order("BTCUSDT", "SELL", str(cantidad))
                    client.enviar_telegram("📉 *SHORT EJECUTADO AUTOMÁTICAMENTE*")

            # 3. Reporte de Vida (Cada 1 hora)
            if (datetime.now() - ultima_alerta_vida) > timedelta(hours=1):
                client.enviar_telegram(f"💓 *CENTINELA ACTIVO*\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`")
                ultima_alerta_vida = datetime.now()

        except Exception as e:
            print(f"Error en el ciclo del worker: {e}")
        
        # Espera 15 segundos entre revisiones para no saturar la API
        time.sleep(15)

if __name__ == "__main__":
    ejecutar_bot()
