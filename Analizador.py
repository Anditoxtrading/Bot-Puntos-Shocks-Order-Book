import json
import asyncio
import requests


# 📌 Función para leer el archivo JSON
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

# 📌 Función para formatear números grandes
def formatear_volumen(num):
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}b"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}m"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}k"
    else:
        return f"{num:.2f}"

# 📌 Función para analizar los libros de órdenes
async def analizar_libro_ordenes():
    while True:
        order_books = cargar_libro_ordenes()
        if not order_books:
            print("No hay datos para analizar. Esperando al próximo ciclo...")
            await asyncio.sleep(1800)  # Esperar 30 minutos antes de otro análisis
            continue

        for symbol, order_book in order_books.items():
            tick_size = obtener_tick_size(symbol)  # Solo obtenemos el tick_size desde Binance

            if tick_size is None:
                print(f"No se pudo obtener tick_size para {symbol}, saltando...")
                continue

            tick_size = float(tick_size)
            price_range = tick_size * 100  # 📌 Ajuste en la agrupación de datos

            bid_ranges = {}
            ask_ranges = {}

            # 📌 Agrupar órdenes de compra (bids)
            for price, qty in order_book['bids'].items():
                price, qty = float(price), float(qty)
                range_key = int(price // price_range) * price_range

                if range_key not in bid_ranges:
                    bid_ranges[range_key] = {'total_qty': 0, 'price_count': {}}

                bid_ranges[range_key]['total_qty'] += qty
                bid_ranges[range_key]['price_count'][price] = bid_ranges[range_key]['price_count'].get(price, 0) + qty

            # 📌 Agrupar órdenes de venta (asks)
            for price, qty in order_book['asks'].items():
                price, qty = float(price), float(qty)
                range_key = int(price // price_range) * price_range

                if range_key not in ask_ranges:
                    ask_ranges[range_key] = {'total_qty': 0, 'price_count': {}}

                ask_ranges[range_key]['total_qty'] += qty
                ask_ranges[range_key]['price_count'][price] = ask_ranges[range_key]['price_count'].get(price, 0) + qty

            # 📌 Obtener las 5 zonas con mayor volumen en bids y asks
            top_bid_ranges = sorted(bid_ranges.items(), key=lambda x: x[1]['total_qty'], reverse=True)[:6]
            top_ask_ranges = sorted(ask_ranges.items(), key=lambda x: x[1]['total_qty'], reverse=True)[:6]

            # 📌 Ordenar listas
            top_bid_ranges = sorted(top_bid_ranges, key=lambda x: x[0], reverse=True)  # De mayor a menor
            top_ask_ranges = sorted(top_ask_ranges, key=lambda x: x[0])  # De menor a mayor

            # 📌 Crear mensaje para Telegram con formato mejorado
            mensaje = f"\n===== {symbol} =====\n"
            mensaje += "<b>Top Long Zones (Compra):</b>\n"
            for price_range, data in top_bid_ranges[2:]:
                most_common_price = max(data['price_count'], key=data['price_count'].get)
                volumen_formateado = formatear_volumen(data['total_qty'])
                mensaje += f"Shock: {most_common_price:.6f} | Volumen: {volumen_formateado} \n"

            mensaje += "\n<b>Top Short Zones (Venta):</b>\n"
            for price_range, data in top_ask_ranges[2:]:
                most_common_price = max(data['price_count'], key=data['price_count'].get)
                volumen_formateado = formatear_volumen(data['total_qty'])
                mensaje += f"Shock: {most_common_price:.6f} | Volumen: {volumen_formateado} \n"

            if mensaje:
                print(mensaje)


        print("Análisis completado.")
        await asyncio.sleep(1800)  # Esperar 30 minutos antes de otro análisis

# 📌 Iniciar el análisis en un bucle asíncrono
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(analizar_libro_ordenes())
