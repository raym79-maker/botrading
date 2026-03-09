import time, os
from datetime import datetime, timedelta
from binance_client import BinanceClient

def ejecutar_centinela():
    client = BinanceClient()
    print("🚀 Worker iniciado. Vigilando el mercado 24/7...")
    
    # Variables de control
    estado_actual = "NEUTRAL"
    ultima_alerta_vida = datetime.now()

    while True:
        try:
            # 1. Obtener indicadores
            rsi, ema, precio_actual = client.get_indicators()
            posicion = client.get_open_positions("BTCUSDT")
            
            # 2. Lógica de Diagnóstico y Telegram
            dist_ema = abs(precio_actual - ema)
            nuevo_estado = ""
            msg_diag = ""

            # Definición de estados (Misma lógica que en app.py)
            if 35 < rsi < 55:
                nuevo_estado = "NEUTRAL"
                msg_diag = f"🟡 RSI Neutral ({rsi:.2f}). Precio: ${precio_actual:,.2f}"
            elif rsi <= 35:
                if precio_actual > ema:
                    nuevo_estado = "OPORTUNIDAD_LONG"
                    msg_diag = f"🎯 Oportunidad LONG! RSI: {rsi:.2f}. Precio: ${precio_actual:,.2f}"
                else:
                    nuevo_estado = "FILTRO_LONG"
                    msg_diag = f"🔴 Filtro EMA: Bajo la EMA por ${dist_ema:.2f}"
            elif rsi >= 55:
                if precio_actual < ema:
                    nuevo_estado = "OPORTUNIDAD_SHORT"
                    msg_diag = f"🎯 Oportunidad SHORT! RSI: {rsi:.2f}. Precio: ${precio_actual:,.2f}"
                else:
                    nuevo_estado = "FILTRO_SHORT"
                    msg_diag = f"🔴 Filtro EMA: Sobre la EMA por ${dist_ema:.2f}"

            # Enviar alerta por cambio de estado
            if nuevo_estado != estado_actual:
                client.enviar_telegram(msg_diag)
                estado_actual = nuevo_estado

            # 3. Lógica de Trading Automático
            if not posicion:
                # Aquí puedes leer la configuración de tu DB o usar valores fijos
                usdt_riesgo = 50.0 
                lev = 20
                cantidad = round((usdt_riesgo * lev) / precio_actual, 3)

                if nuevo_estado == "OPORTUNIDAD_LONG":
                    client.place_order("BTCUSDT", "BUY", str(cantidad))
                    client.enviar_telegram("🚀 EJECUTADO: AUTO LONG")
                elif nuevo_estado == "OPORTUNIDAD_SHORT":
                    client.place_order("BTCUSDT", "SELL", str(cantidad))
                    client.enviar_telegram("📉 EJECUTADO: AUTO SHORT")

            # 4. Heartbeat (1 Hora)
            if (datetime.now() - ultima_alerta_vida) > timedelta(hours=1):
                client.enviar_telegram(f"💓 Worker Activo | BTC: ${precio_actual:,.2f} | RSI: {rsi:.2f}")
                ultima_alerta_vida = datetime.now()

        except Exception as e:
            print(f"Error en el worker: {e}")
            time.sleep(10) # Esperar un poco antes de reintentar si hay error de red

        time.sleep(5) # Revisar cada 5 segundos

if __name__ == "__main__":
    ejecutar_centinela()