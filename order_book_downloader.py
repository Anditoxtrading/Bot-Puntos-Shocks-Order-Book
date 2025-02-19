import websocket
import json
import requests
import threading
import asyncio
import time
from binance.client import Client

# Configurar API de Binance
api_key = ''
api_secret = ''
client = Client(api_key=api_key, api_secret=api_secret)

# Obtener monedas que cumplan ciertos criterios
coins = []
futures_exchange_info = client.futures_ticker()
for element in futures_exchange_info:
    if 'USDT' in element['symbol'] and float(element['quoteVolume']) > 200000000.00 and float(element['lastPrice']) < 5:
        coins.append(element['symbol'])
order_books = {symbol: {"bids": {}, "asks": {}} for symbol in coins}
print(coins)
# Crear un bloqueo para evitar conflictos de acceso
order_book_lock = threading.Lock()

# Obtener instantánea del libro de órdenes desde la API
def get_order_book_snapshot(symbol):
    url = f"https://fapi.binance.com/fapi/v1/depth?symbol={symbol}&limit=1000"
    response = requests.get(url)
    return response.json()

# Actualizar el libro de órdenes local con las actualizaciones del WebSocket
def update_order_book(order_book, update):
    with order_book_lock:  # Bloqueo al modificar el diccionario
        for price, qty in update['b']:  # Bids
            if float(qty) == 0:
                order_book['bids'].pop(price, None)
            else:
                order_book['bids'][price] = qty

        for price, qty in update['a']:  # Asks
            if float(qty) == 0:
                order_book['asks'].pop(price, None)
            else:
                order_book['asks'][price] = qty

# WebSocket: Manejo de mensajes
def on_message(ws, message, symbol):
    data = json.loads(message)['data']
    update_order_book(order_books[symbol], data)

# Función para guardar el estado del libro de órdenes en un archivo JSON
def save_order_books():
    with order_book_lock:  # Bloqueo al acceder a los datos
        with open("order_books.json", "w", encoding="utf-8") as f:
            json.dump(order_books, f, indent=4)
    print("Order books saved to order_books.json")

# WebSocket de apertura
def on_open(ws):
    print("WebSocket connection opened.")

# WebSocket de error
def on_error(ws, error):
    print(f"WebSocket error: {error}")

# WebSocket de cierre
def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed.")

# Iniciar WebSocket para cada moneda
def start_websocket(symbol):
    ws = websocket.WebSocketApp(
        f"wss://fstream.binance.com/stream?streams={symbol.lower()}@depth@100ms",
        on_message=lambda ws, msg: on_message(ws, msg, symbol),
        on_open=on_open,
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever()

# Función que guarda los libros de órdenes cada hora
def save_every_hour():
    while True:
        time.sleep(10) 
        save_order_books()

async def main():
    # Obtener la instantánea de los libros de órdenes al inicio
    for symbol in coins:
        snapshot = get_order_book_snapshot(symbol)
        with order_book_lock:
            for bid in snapshot['bids']:
                order_books[symbol]['bids'][bid[0]] = bid[1]
            for ask in snapshot['asks']:
                order_books[symbol]['asks'][ask[0]] = ask[1]

    # Iniciar WebSocket en hilos separados para cada moneda
    threads = []
    for symbol in coins:
        thread = threading.Thread(target=start_websocket, args=(symbol,))
        threads.append(thread)
        thread.start()

    # Hilo separado para guardar los libros de órdenes cada hora
    save_thread = threading.Thread(target=save_every_hour, daemon=True)
    save_thread.start()

# Ejecutar la función principal con asyncio
if __name__ == "__main__":
    asyncio.run(main())
