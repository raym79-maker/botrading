import logging
from binance_client import BinanceClient

# Configuración del Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_trading.log"), 
        logging.StreamHandler()                 
    ]
)

# Inicializamos el cliente
client = BinanceClient()

def ejecutar_ciclo(objetivo_compra=95000):
    try:
        logging.info("Iniciando ciclo de verificación...")
        
        # Obtenemos datos del mercado
        saldo = client.get_balance()
        precio = client.get_price("BTCUSDT")
        
        logging.info(f"Saldo: {saldo} USDT | Precio BTC: {precio} USDT")
        
        # Aquí la indentación debe ser exacta (usualmente 8 espacios respecto al inicio)
        if precio <= objetivo_compra:
            logging.warning(f"¡Precio {precio} <= {objetivo_compra}! Ejecutando orden de compra...")
            try:
                # Calculamos una cantidad que sume al menos 105 USDT para estar seguros
                cantidad_calculada = round(105 / precio, 3) 
                orden = client.place_order("BTCUSDT", "BUY", str(cantidad_calculada))
                logging.info(f"Orden ejecutada: {cantidad_calculada} BTC. ID: {orden['orderId']}")
            except Exception as e:
                logging.error(f"Fallo al ejecutar la compra: {e}")
        else:
            logging.info(f"El precio se mantiene por encima del objetivo ({objetivo_compra}).")
            
    except Exception as e:
        logging.error(f"Error en el ciclo de ejecución: {e}")

if __name__ == "__main__":
    ejecutar_ciclo()