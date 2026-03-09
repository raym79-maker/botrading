import time, os
from datetime import datetime, timedelta
from binance_client import BinanceClient

def bot_permanente():
    client = BinanceClient()
    estado_previo = "NEUTRAL"
    ultima_alerta = datetime.now()
    print("🚀 Worker activo. Vigilando mercado...")

    while True:
        try:
            rsi, ema, precio = client.get_indicators()
            pos = client.get_open_positions()
            
            if precio == 0:
                print("⚠️ Error de conexión. Reintentando...")
                time.sleep(15) ; continue

            # Lógica de Trading
            estado = "NEUTRAL"
            if rsi <= 35:
                estado = "OPORTUNIDAD_LONG" if precio > ema else "FILTRO_LONG"
            elif rsi >= 55:
                estado = "OPORTUNIDAD_SHORT" if precio < ema else "FILTRO_SHORT"

            # Alerta Telegram
            if estado != estado_previo:
                client.enviar_telegram(f"📢 Worker Signal: {estado}\nPrecio: ${precio:,.2f}")
                estado_previo = estado

            # Apertura Auto (Margen 50 USDT x20)
            if not pos:
                cantidad = round((50.0 * 20) / precio, 3) 
                if estado == "OPORTUNIDAD_LONG":
                    client.place_order("BTCUSDT", "BUY", str(cantidad))
                    client.enviar_telegram("🚀 *AUTO LONG EJECUTADO*")
                elif estado == "OPORTUNIDAD_SHORT":
                    client.place_order("BTCUSDT", "SELL", str(cantidad))
                    client.enviar_telegram("📉 *AUTO SHORT EJECUTADO*")

            # Reporte de Vida
            if (datetime.now() - ultima_alerta) > timedelta(hours=1):
                client.enviar_telegram(f"💓 Bot Activo | BTC ${precio:,.2f}")
                ultima_alerta = datetime.now()

        except Exception as e:
            print(f"Error en el ciclo: {e}")
        
        time.sleep(20)

if __name__ == "__main__":
    bot_permanente()
