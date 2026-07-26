import asyncio
import json
import math
import websockets
import aiohttp
import threading
import time
import keyboard
import numpy as np
import os
import signal
import winsound
import argparse
try:
    from osc_commands import OSCCommands
except ImportError:
    print("Помилка імпорту. Переконайтеся, що бібліотека python-osc встановлено.")
    OSCCommands = None

# --- Глобальні змінні та налаштування ---

# Змінні для калібрування
delta_accX = 0.0
delta_accY = 0.0
delta_accZ = 0.0

# Стан калібрування
class CalibrationState:
    IDLE = 0
    CALIBRATING = 1
    DONE = 2

calibration_state = CalibrationState.IDLE
calibration_data = []

# Множина для зберігання всіх підключених клієнтів WebSocket
CONNECTED_CLIENTS = set()

# Словник для зберігання останніх даних з сенсорів, включаючи розраховані кути
SENSOR_DATA = {
    "accX": 0,
    "accY": 0,
    "angle_x": 0,
    "angle_y": 0
}

# Базова частина IP-адреси
BASE_IP = "192.168.0."
DEFAULT_PORT = 8080

# URL-адреса HTTP-сервера, звідки беруться дані (буде встановлена після пошуку)
HTTP_SERVER_URL = None

# Коефіцієнт масштабування для перетворення значень акселерометра в кути
# Визначено експериментально: accX=5.0 при 30°, accX=8.45 при 45°
SCALING_FACTOR = 11.0

# Коефіцієнт згладжування для фільтра (EMA)
# 0.2 = сильне згладжування, 0.8 = слабке згладжування
ALPHA = 0.3

# Фільтровані значення
filtered_accX = 0.0
filtered_accY = 0.0
filtered_accZ = 0.0

# Файл конфігурації
CONFIG_FILE = "config.json"

def clamp(value, min_val, max_val):
    """Допоміжна функція, що обмежує значення в заданому діапазоні [min_val, max_val]."""
    return max(min_val, min(value, max_val))

def load_config():
    """
    Завантажує конфігурацію з файлу.
    Повертає словник з конфігурацією або порожній словник.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                print(f"Завантажено конфігурацію: {config}")
                return config
        except (json.JSONDecodeError, IOError) as e:
            print(f"Помилка читання конфігурації: {e}")
    return {}

def save_config(config):
    """
    Зберігає конфігурацію у файл.
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Конфігурацію збережено: {config}")
    except IOError as e:
        print(f"Помилка запису конфігурації: {e}")

async def check_server_available(session, ip_address):
    """
    Перевіряє доступність HTTP-сервера за вказаною IP-адресою.
    Повертає True, якщо сервер доступний і повертає коректні дані.
    """
    url = f"http://{ip_address}:{DEFAULT_PORT}/get?accX&accY&accZ"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
            if response.status == 200:
                data = await response.json()
                # Перевіряємо, чи є дані в буфері (не null)
                accX = data.get("buffer", {}).get("accX", {}).get("buffer", [None])[0]
                accY = data.get("buffer", {}).get("accY", {}).get("buffer", [None])[0]
                accZ = data.get("buffer", {}).get("accZ", {}).get("buffer", [None])[0]
                if accX is not None and accY is not None and accZ is not None:
                    return True, url
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError):
        pass
    return False, None

async def find_server():
    """
    Шукає доступний HTTP-сервер, перевіряючи діапазони адрес 100-105 та 160-165.
    Повертає URL знайденого сервера або None, якщо сервер не знайдено.
    """
    async with aiohttp.ClientSession() as session:
        # Перший діапазон: 100-110
        print("Пошук сервера в діапазоні 192.168.0.100-105...")
        for i in range(100, 105):
            ip = f"{BASE_IP}{i}"
            available, url = await check_server_available(session, ip)
            if available:
                print(f"Знайдено сервер: {url}")
                return url
        
        # Другий діапазон: 161-170
        print("Пошук сервера в діапазоні 192.168.0.160-165...")
        for i in range(160, 165):
            ip = f"{BASE_IP}{i}"
            available, url = await check_server_available(session, ip)
            if available:
                print(f"Знайдено сервер: {url}")
                return url
    
    return None

def get_user_ip():
    """
    Запитує у користувача власне значення IP-адреси.
    """
    while True:
        try:
            user_input = input("Введіть останнє число IP-адреси (наприклад, 111 або 165): ")
            last_octet = int(user_input)
            if 1 <= last_octet <= 254:
                url = f"http://{BASE_IP}{last_octet}:{DEFAULT_PORT}/get?accX&accY&accZ"
                print(f"Використовується адреса: {url}")
                return url
            else:
                print("Число має бути в діапазоні від 1 до 254.")
        except ValueError:
            print("Будь ласка, введіть коректне число.")

async def register_client(websocket):
    """
    Реєструє нового клієнта, що підключився, 
    і утримує з'єднання відкритим до його закриття.
    """
    CONNECTED_CLIENTS.add(websocket)
    print(f"Новий клієнт підключився. Всього клієнтів: {len(CONNECTED_CLIENTS)}")
    try:
        # Очікуємо, поки клієнт не від'єднається
        await websocket.wait_closed()
    finally:
        # Видаляємо клієнта з множини після від'єднання
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Клієнт від'єднався. Всього клієнтів: {len(CONNECTED_CLIENTS)}")

async def data_loop(osc_sender=None, run_threshold=1.5):
    """
    Головний цикл програми: періодично запитує дані з HTTP-сервера,
    обчислює кути нахилу та транслює їх усім підключеним клієнтам.
    """
    global calibration_state, delta_accX, delta_accY, delta_accZ, calibration_data, filtered_accX, filtered_accY, filtered_accZ

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(HTTP_SERVER_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        raw_accX = data.get("buffer", {}).get("accX", {}).get("buffer", [0])[0]
                        raw_accY = data.get("buffer", {}).get("accY", {}).get("buffer", [0])[0]
                        raw_accZ = data.get("buffer", {}).get("accZ", {}).get("buffer", [0])[0]

                        accX = raw_accX
                        accY = raw_accY
                        accZ = raw_accZ

                        if calibration_state == CalibrationState.CALIBRATING:
                            calibration_data.append((accX, accY, accZ))
                            continue

                        if calibration_state == CalibrationState.DONE:
                            accX -= delta_accX
                            accY -= delta_accY
                            accZ -= delta_accZ
                        
                        if osc_sender:
                            osc_sender.send_commands(raw_accX, raw_accY, raw_accZ, delta_accX, delta_accY, delta_accZ, run_threshold=run_threshold)

                        # Застосовуємо фільтр низьких частот (EMA)
                        filtered_accX = ALPHA * accX + (1 - ALPHA) * filtered_accX
                        filtered_accY = ALPHA * accY + (1 - ALPHA) * filtered_accY
                        filtered_accZ = ALPHA * accZ + (1 - ALPHA) * filtered_accZ

                        ratio_x = clamp(filtered_accX / SCALING_FACTOR, -1.0, 1.0)
                        ratio_y = clamp(filtered_accY / SCALING_FACTOR, -1.0, 1.0)

                        angle_x = math.degrees(math.asin(ratio_x))
                        angle_y = math.degrees(math.asin(ratio_y))

                        SENSOR_DATA.update({
                            "accX": filtered_accX, "accY": filtered_accY, "accZ": filtered_accZ,
                            "angle_x": angle_x, "angle_y": angle_y
                        })
                    else:
                        print(f"Помилка отримання даних: HTTP {response.status}")
            except aiohttp.ClientError as e:
                print(f"Помилка підключення до HTTP-сервера: {e}")
            except json.JSONDecodeError:
                print("Помилка: не вдалося розкодувати JSON.")

            if CONNECTED_CLIENTS:
                message = json.dumps({
                    "accX": SENSOR_DATA["accX"],
                    "accY": SENSOR_DATA["accY"],
                    "accZ": SENSOR_DATA["accZ"],
                    "angle_x": SENSOR_DATA["angle_x"],
                    "angle_y": SENSOR_DATA["angle_y"]
                })
                # Використовуємо gather з return_exceptions=True, щоб уникнути падіння циклу,
                # якщо один з клієнтів від'єднався.
                await asyncio.gather(*[client.send(message) for client in CONNECTED_CLIENTS], return_exceptions=True)

            await asyncio.sleep(0.05)  # 20 Гц

def calibration_thread(config):
    """
    Потік для виконання калібрування.
    """
    global calibration_state, delta_accX, delta_accY, delta_accZ, calibration_data
    
    print("Режим калібрування. Тримайте смартфон у стані спокою впродовж 5 секунд")
    calibration_data = []
    calibration_state = CalibrationState.CALIBRATING
    
    for i in range(3, -1, -1):
        if i == 0:
            print(f"{i} .......")
            winsound.Beep(1000, 700)
        else:
            print(f"{i} ...")
            winsound.Beep(1000, 200)
        time.sleep(1)
        
    if calibration_data:
        accX_data, accY_data, accZ_data = zip(*calibration_data)
        delta_accX = np.mean(accX_data)
        delta_accY = np.mean(accY_data)
        delta_accZ = np.mean(accZ_data)
        print(f"Калібрування завершено: delta_accX={delta_accX:.2f}, delta_accY={delta_accY:.2f}, delta_accZ={delta_accZ:.2f}")
        
        config["delta_accX"] = delta_accX
        config["delta_accY"] = delta_accY
        config["delta_accZ"] = delta_accZ
        save_config(config)
    else:
        print("Не вдалося отримати дані для калібрування.")

    calibration_state = CalibrationState.DONE

import os
import signal

def input_handler(config):
    """
    Обробник введення з клавіатури для керування програмою.
    """
    global calibration_state
    
    while True:
        key = keyboard.read_key()
        if key == 'f1' or key == 'F1':
            if calibration_state != CalibrationState.CALIBRATING:
                cal_thread = threading.Thread(target=calibration_thread, args=(config,))
                cal_thread.start()
        elif key == 'esc':
            print("Завершення роботи...")
            os.kill(os.getpid(), signal.SIGINT)
            break
        time.sleep(0.1)


async def main_async(osc_sender=None, use_websocket=False, run_threshold=1.5, config=None):
    """Основна функція, яка запускає WebSocket-сервер та цикл обробки даних."""
    global HTTP_SERVER_URL, delta_accX, delta_accY, delta_accZ, calibration_state
    
    saved_ip = config.get("server_ip")
    
    # Load calibration from config if available
    if "delta_accX" in config and "delta_accY" in config and "delta_accZ" in config:
        delta_accX = config["delta_accX"]
        delta_accY = config["delta_accY"]
        delta_accZ = config["delta_accZ"]
        if delta_accX != 0.0 or delta_accY != 0.0 or delta_accZ != 0.0:
            calibration_state = CalibrationState.DONE
            print(f"Завантажено збережене калібрування: delta_accX={delta_accX:.2f}, delta_accY={delta_accY:.2f}, delta_accZ={delta_accZ:.2f}")

    server_url = None
    
    # Спершу перевіряємо збережену адресу
    if saved_ip:
        print(f"Перевірка збереженої адреси: {saved_ip}...")
        async with aiohttp.ClientSession() as session:
            available, url = await check_server_available(session, saved_ip)
            if available:
                print(f"Знайдено сервер за збереженою адресою: {url}")
                server_url = url
            else:
                print("Збережена адреса недоступна. Пошук нового сервера...")
    
    # Якщо збережена адреса не працює, шукаємо сервер
    if server_url is None:
        server_url = await find_server()
    
    # Якщо сервер не знайдено, запитуємо адресу у користувача
    if server_url is None:
        print("\nНе вдалося знайти сервер у діапазонах 192.168.0.100-110 та 192.168.0.161-170.")
        print("Будь ласка, введіть адресу сервера вручну.")
        server_url = get_user_ip()
    
    ip_to_save = server_url.split("//")[1].split(":")[0]
    config["server_ip"] = ip_to_save
    save_config(config)
    
    HTTP_SERVER_URL = server_url
    print(f"Підключення до сервера: {HTTP_SERVER_URL}")
    
    server = None
    if use_websocket:
        server = await websockets.serve(register_client, "localhost", 8767)
        print("WebSocket-сервер запущено на ws://localhost:8767")
    else:
        print("WebSocket-сервер не запущено (використовуйте --websocket для активації).")
    
    # Always print keyboard control hints
    print("Клавіші керування: F1 - калібрування стану спокою, Esc - завершення роботи")

    data_task = asyncio.create_task(data_loop(osc_sender=osc_sender, run_threshold=run_threshold))

    try:
        await data_task
    except asyncio.CancelledError:
        pass
    finally:
        if server:
            server.close()
            await server.wait_closed()

def main():
    global HTTP_SERVER_URL

    config = load_config()
    debug_mode = config.get("debug", False)
    thresholds = config.get("thresholds", {})
    run_threshold = thresholds.get("run", 1.5)
    move_threshold = thresholds.get("move", 0.5)
    startup_mode = config.get("startup_mode", {})

    parser = argparse.ArgumentParser(description="WebSocket-сервер для трансляції даних з акселерометра.")
    parser.add_argument("--osc", action="store_true", help="Активувати режим надсилання OSC команд (перевизначає конфігурацію).")
    parser.add_argument("--websocket", action="store_true", help="Активувати WebSocket сервер (перевизначає конфігурацію).")
    args = parser.parse_args()

    use_osc = args.osc or startup_mode.get("osc", False)
    use_websocket = args.websocket or startup_mode.get("websocket", False)
    
    if use_osc and not OSCCommands:
        print("Режим --osc неможливий, оскільки не вдалося імпортувати OSCCommands.")
        return

    osc_sender = None
    if use_osc:
        osc_bindings = config.get("osc_bindings", [])
        osc_sender = OSCCommands(debug=debug_mode, osc_bindings=osc_bindings)

    input_thread = threading.Thread(target=input_handler, args=(config,))
    input_thread.daemon = True
    input_thread.start()

    try:
        asyncio.run(main_async(osc_sender=osc_sender, use_websocket=use_websocket, run_threshold=run_threshold, move_threshold=move_threshold, config=config))
    except KeyboardInterrupt:
        print("\nПрограму зупинено.")
    finally:
        if osc_sender:
            osc_sender.release_all_commands()


# Точка входу в програму
if __name__ == "__main__":
    main()
