import time
import os
from datetime import datetime, timedelta
from binance_client import BinanceClient

def main():
    client = BinanceClient()
    # Variables de estado locales (no se borran al cerrar el navegador)
    max_price = 0.0
    estado_actual = "NEUTRAL"
    ultima_alerta_vida = datetime.now() - timedelta(hours=1) # Para enviar la primera de inmediato

    print("🚀 Worker Centinela 24/7 Iniciado...")
    client.enviar_telegram("🤖 *MOTOR TRADING 24/7 ACTIVADO*\nEl bot ahora opera de forma independiente al navegador.")

    while True:
        try:
            # 1. Obtener indicadores (Kraken + Binance)
            rsi, ema, precio_actual = client.get_indicators()
            
            if precio_actual == 0:
                time.sleep(10)
                continue

            # 2. Verificar posición actual
            posicion = client.get_open_positions("BTCUSDT")
            
            if posicion:
                side = "LONG" if float(posicion['positionAmt']) > 0 else "SHORT"
                entry_p = float(posicion['entryPrice'])
                tamano = abs(float(posicion['positionAmt']))
                
                # Lógica de Trailing Stop
                distancia_ts = 500.0 # Puedes sacarla de una DB si quieres que sea dinámica
                
                if max_price == 0: max_price = precio_actual
                
                if side == "LONG":
                    if precio_actual > max_price: max_price = precio_actual
                    if precio_actual <= (max_price - distancia_ts):
                        pnl = (precio_actual - entry_p) * tamano
                        client.place_order("BTCUSDT", "SELL", str(tamano))
                        client.registrar_trade(side, entry_p, precio_actual, pnl)
                        client.enviar_telegram(f"🛡️ *CIERRE TRAILING (LONG)*\nPNL: `{pnl:.2f} USDT`")
                        max_price = 0
                else:
                    if max_price == 0 or precio_actual < max_price: max_price = precio_actual
                    if precio_actual >= (max_price + distancia_ts):
                        pnl = (entry_p - precio_actual) * tamano
                        client.place_order("BTCUSDT", "BUY", str(tamano))
                        client.registrar_trade(side, entry_p, precio_actual, pnl)
                        client.enviar_telegram(f"🛡️ *CIERRE TRAILING (SHORT)*\nPNL: `{pnl:.2f} USDT`")
                        max_price = 0
            
            else:
                # 3. Lógica de Apertura Automática (Sin posición)
                max_price = 0
                usdt_riesgo = 50.0 # Margen fijo para el worker
                lev = 20
                
                if rsi > 0:
                    cantidad_op = round((usdt_riesgo * lev) / precio_actual, 3)
                    
                    if rsi <= 35 and precio_actual > ema:
                        client.place_order("BTCUSDT", "BUY", str(cantidad_op))
                        client.enviar_telegram(f"🚀 *NUEVA POSICIÓN (LONG)*\nMargen: `{usdt_riesgo} USDT`")
                    elif rsi >= 55 and precio_actual < ema:
                        client.place_order("BTCUSDT", "SELL", str(cantidad_op))
                        client.enviar_telegram(f"📉 *NUEVA POSICIÓN (SHORT)*\nMargen: `{usdt_riesgo} USDT`")

            # 4. Heartbeat (Reporte de vida cada hora)
            if (datetime.now() - ultima_alerta_vida) > timedelta(hours=1):
                client.enviar_telegram(f"💓 *CENTINELA 24/7 OK*\nBTC: `${precio_actual:,.2f}` | RSI: `{rsi:.2f}`")
                ultima_alerta_vida = datetime.now()

        except Exception as e:
            print(f"Error en el bucle del worker: {e}")
            time.sleep(30) # Esperar antes de reintentar si hay error de red
        
        time.sleep(15) # Frecuencia de chequeo del motor

if __name__ == "__main__":
    main()
