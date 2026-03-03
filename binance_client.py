import requests, time, hmac, hashlib, csv, os
from datetime import datetime

class BinanceClient:
    def __init__(self):
        # En Railway, estas variables deben estar en la pestaña "Variables" del dashboard
        self.api_key = os.getenv("API_KEY")
        self.secret_key = os.getenv("SECRET_KEY")
        self.base_url = 'https://demo-fapi.binance.com'
        self.public_url = 'https://fapi.binance.com' # URL real para el precio

    def _get_signature(self, params):
        return hmac.new(self.secret_key.encode('utf-8'), params.encode('utf-8'), hashlib.sha256).hexdigest()

    def _get_timestamp(self):
        return int(time.time() * 1000)

    def get_price(self, symbol="BTCUSDT"):
        """Consulta el precio real usando la API pública para evitar bloqueos en la nube."""
        try:
            # Usamos la URL pública (fapi.binance.com) que es más estable para el ticker
            url = f"{self.public_url}/fapi/v1/ticker/price?symbol={symbol}"
            response = requests.get(url, timeout=5)
            data = response.json()
            return float(data['price'])
        except Exception as e:
            # Si falla, intentamos con la base_url de demo como respaldo
            try:
                res = requests.get(f"{self.base_url}/fapi/v1/ticker/price?symbol={symbol}", timeout=5).json()
                return float(res['price'])
            except:
                return 0.0

    def place_order(self, symbol, side, quantity):
        params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity, "timestamp": self._get_timestamp()}
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        sig = self._get_signature(query_string)
        headers = {'X-MBX-APIKEY': self.api_key}
        return requests.post(f"{self.base_url}/fapi/v1/order?{query_string}&signature={sig}", headers=headers).json()

    def get_open_positions(self, symbol="BTCUSDT"):
        params = {"timestamp": self._get_timestamp()}
        query_string = f"timestamp={params['timestamp']}"
        sig = self._get_signature(query_string)
        headers = {'X-MBX-APIKEY': self.api_key}
        data = requests.get(f"{self.base_url}/fapi/v2/account?{query_string}&signature={sig}", headers=headers).json()
        if 'positions' in data:
            for pos in data['positions']:
                if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0:
                    return pos
        return None

    def registrar_trade(self, side, entry, exit, pnl):
        archivo = "historial_trades.csv"
        existe = os.path.exists(archivo)
        with open(archivo, "a", newline='') as f:
            writer = csv.writer(f)
            if not existe or os.stat(archivo).st_size == 0:
                writer.writerow(["Fecha", "Side", "Entrada", "Salida", "PNL (USDT)"])
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), side, entry, exit, round(pnl, 2)])
