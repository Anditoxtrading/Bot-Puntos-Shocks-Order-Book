import json
import asyncio
import requests


# Función para leer el archivo JSON
def cargar_libro_ordenes(ruta_archivo="order_books.json"):
    try:
        with open(ruta_archivo, "r") as file:
            data = json.load(file)
        return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error al cargar el libro de órdenes: {e}")
        return {}

def obtener_tick_size(symbol):
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        response = requests.get(url)
        data = response.json()
        for s in data['symbols']:
            if s['symbol'] == symbol:
                for filtro in s['filters']:
                    if filtro['filterType'] == 'PRICE_FILTER':
                        return float(filtro['tickSize'])
        print(f"No se encontró tick_size para {symbol}")
        return None
    except Exception as e:
        print(f"Error al obtener tick_size para {symbol}: {e}")
        return None

def obtener_precio_actual(symbol):
    """Obtiene el precio actual del símbolo desde Binance."""
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        return float(data['price'])
    except Exception as e:
        print(f"Error al obtener precio actual para {symbol}: {e}")
        return None

def calcular_rango_agregacion(tick_size, precio_actual):
    """
    Calcula un rango de agrupación adecuado según el precio actual.
    Se definen los rangos base de la siguiente forma:
      - Si precio < 0.001: rango_base = 0.00001
      - Si 0.001 <= precio < 0.01: rango_base = 0.0001
      - Si 0.01 <= precio < 0.1: rango_base = 0.001
      - Si 0.1 <= precio < 1: rango_base = 0.01
      - Si 1 <= precio < 10: rango_base = 0.1
      - Si 10 <= precio < 100: rango_base = 1
      - Si 100 <= precio < 1000: rango_base = 10
      - De lo contrario: rango_base = 100
    """
    if precio_actual < 0.001:
        rango_base = 0.00001
    elif precio_actual < 0.01:
        rango_base = 0.0001
    elif precio_actual < 0.1:
        rango_base = 0.001
    elif precio_actual < 1:
        rango_base = 0.01
    elif precio_actual < 10:
        rango_base = 0.1
    elif precio_actual < 100:
        rango_base = 1
    elif precio_actual < 1000:
        rango_base = 10
    else:
        rango_base = 100
    return rango_base

# Función para formatear números grandes
def formatear_volumen(num):
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}b"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}m"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}k"
    else:
        return f"{num:.2f}"

# Función para analizar los libros de órdenes
async def analizar_libro_ordenes():
    while True:
        order_books = cargar_libro_ordenes()
        if not order_books:
            print("No hay datos para analizar. Esperando al próximo ciclo...")
            await asyncio.sleep(1800)  # Esperar 30 minutos antes de otro análisis
            continue

        for symbol, order_book in order_books.items():
            tick_size = obtener_tick_size(symbol)
            if tick_size is None:
                print(f"No se pudo obtener tick_size para {symbol}, saltando...")
                continue
            tick_size = float(tick_size)

            precio_actual = obtener_precio_actual(symbol)
            if precio_actual is None:
                print(f"No se pudo obtener precio actual para {symbol}, saltando...")
                continue

            # Calcula el rango de agrupación dinámico basándose en el precio actual
            price_range = calcular_rango_agregacion(tick_size, precio_actual)
            bid_ranges = {}
            ask_ranges = {}

            # Agrupar órdenes de compra (bids)
            for price, qty in order_book['bids'].items():
                price, qty = float(price), float(qty)
                range_key = int(price // price_range) * price_range
                if range_key not in bid_ranges:
                    bid_ranges[range_key] = {'total_qty': 0, 'price_count': {}}
                bid_ranges[range_key]['total_qty'] += qty
                bid_ranges[range_key]['price_count'][price] = bid_ranges[range_key]['price_count'].get(price, 0) + qty

            # Agrupar órdenes de venta (asks)
            for price, qty in order_book['asks'].items():
                price, qty = float(price), float(qty)
                range_key = int(price // price_range) * price_range
                if range_key not in ask_ranges:
                    ask_ranges[range_key] = {'total_qty': 0, 'price_count': {}}
                ask_ranges[range_key]['total_qty'] += qty
                ask_ranges[range_key]['price_count'][price] = ask_ranges[range_key]['price_count'].get(price, 0) + qty

            # Obtener las zonas con mayor volumen en bids y asks (tomando 6 niveles y omitiendo los dos primeros)
            top_bid_ranges = sorted(bid_ranges.items(), key=lambda x: x[1]['total_qty'], reverse=True)[:6]
            top_ask_ranges = sorted(ask_ranges.items(), key=lambda x: x[1]['total_qty'], reverse=True)[:6]

            # Ordenar listas para presentación
            top_bid_ranges = sorted(top_bid_ranges, key=lambda x: x[0], reverse=True)
            top_ask_ranges = sorted(top_ask_ranges, key=lambda x: x[0])

            # Crear mensaje para Telegram con formato mejorado
            mensaje = f"\n===== {symbol}. =====\n"
            mensaje += "<b>Top Long Zones (Compra):</b>\n"
            for pr_range, data in top_bid_ranges[2:]:
                most_common_price = max(data['price_count'], key=data['price_count'].get)
                volumen_formateado = formatear_volumen(data['total_qty'])
                mensaje += f"Shock: {most_common_price:.6f}. | Volumen: {volumen_formateado}\n"

            mensaje += "\n<b>Top Short Zones (Venta):</b>\n"
            for pr_range, data in top_ask_ranges[2:]:
                most_common_price = max(data['price_count'], key=data['price_count'].get)
                volumen_formateado = formatear_volumen(data['total_qty'])
                mensaje += f"Shock: {most_common_price:.6f}. | Volumen: {volumen_formateado}\n"

            if mensaje:
                print(mensaje)
        print("Análisis completado")
        await asyncio.sleep(1800)

# Iniciar el análisis en un bucle asíncrono
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(analizar_libro_ordenes())
