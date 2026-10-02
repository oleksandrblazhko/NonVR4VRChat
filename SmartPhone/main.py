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


# -------------------------------------------------
# Імпорти
# -------------------------------------------------

try:
    from osc_commands import OSCCommands
except ImportError as e:
    print(f"Помилка імпорту osc_commands: {e}")
    OSCCommands = None


try:
    from smart_calibration import SmartCalibration, DataCollector
except ImportError as e:
    print(f"Помилка імпорту smart_calibration: {e}")
    SmartCalibration = None
    DataCollector = None


try:
    from command_gui import CommandGUI
except ImportError as e:
    print(f"Помилка імпорту command_gui: {e}")
    CommandGUI = None


# --- Глобальні змінні та налаштування ---

keyboard_input_suspended = threading.Event()

smart_cal_lock = threading.Lock()

calibration_values = {
    "delta_accX": 0.0,
    "delta_accY": 0.0,
    "delta_accZ": 0.0
}


# --- Стан калібрування ---

class CalibrationState:
    IDLE = 0
    CALIBRATING = 1
    DONE = 2


calibration_state = CalibrationState.IDLE
calibration_data = []


class SmartCalibrationState:
    IDLE = 0
    COLLECTING_NEUTRAL = 1
    COLLECTING_FORWARD = 2
    COLLECTING_BACKWARD = 3
    COLLECTING_LEFT = 4
    COLLECTING_RIGHT = 5
    DONE = 6


class State:
    def __init__(self, initial_value):
        self._value = initial_value

    def get(self):
        return self._value

    def set(self, new_value):
        self._value = new_value


smart_calibration_state = State(
    SmartCalibrationState.IDLE
)

smart_calibration_data = {
    "neutral": [],
    "forward": [],
    "backward": [],
    "left": [],
    "right": [],
}


# --- WebSocket ---

CONNECTED_CLIENTS = set()


# --- Дані сенсорів ---

SENSOR_DATA = {
    "accX": 0,
    "accY": 0,
    "angle_x": 0,
    "angle_y": 0
}


# --- Мережеві налаштування ---

BASE_IP = "192.168.0."
DEFAULT_PORT = 8080

HTTP_SERVER_URL = None


# --- Обробка акселерометра ---

SCALING_FACTOR = 11.0

ALPHA = 0.3

filtered_accX = 0.0
filtered_accY = 0.0
filtered_accZ = 0.0


# --- Конфігурація ---

CONFIG_FILE = "config.json"


def clamp(value, min_val, max_val):
    """Обмежує значення у заданому діапазоні."""
    return max(min_val, min(value, max_val))


def degrees_to_accel(degrees):
    """
    Перетворює кут у градусах
    у відповідне значення акселерометра.
    """
    return 9.8 * math.sin(math.radians(degrees))


def load_config():
    """
    Завантажує конфігурацію з файлу.
    """
    if os.path.exists(CONFIG_FILE):

        try:

            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)

            print(
                f"Завантажено конфігурацію: {config}"
            )

            return config

        except (json.JSONDecodeError, IOError) as e:

            print(
                f"Помилка читання конфігурації: {e}"
            )

    return {}


def save_config(config):
    """
    Зберігає конфігурацію у файл.
    """
    try:

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

        print(
            f"Конфігурацію збережено: {config}"
        )

    except IOError as e:

        print(
            f"Помилка запису конфігурації: {e}"
        )


async def check_server_available(
    session,
    ip_address
):
    """
    Перевіряє доступність HTTP-сервера.
    """

    url = (
        f"http://{ip_address}:{DEFAULT_PORT}"
        f"/get?accX&accY&accZ"
    )

    try:

        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=2)
        ) as response:

            if response.status == 200:

                data = await response.json()

                accX = (
                    data.get("buffer", {})
                    .get("accX", {})
                    .get("buffer", [None])[0]
                )

                accY = (
                    data.get("buffer", {})
                    .get("accY", {})
                    .get("buffer", [None])[0]
                )

                accZ = (
                    data.get("buffer", {})
                    .get("accZ", {})
                    .get("buffer", [None])[0]
                )

                if (
                    accX is not None
                    and accY is not None
                    and accZ is not None
                ):
                    return True, url

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        json.JSONDecodeError,
        KeyError
    ):
        pass

    return False, None


async def find_server():
    """
    Шукає доступний HTTP-сервер.
    """

    async with aiohttp.ClientSession() as session:

        print(
            "Пошук сервера в діапазоні "
            "192.168.0.100-105..."
        )

        for i in range(100, 105):

            ip = f"{BASE_IP}{i}"

            available, url = (
                await check_server_available(
                    session,
                    ip
                )
            )

            if available:

                print(
                    f"Знайдено сервер: {url}"
                )

                return url

        print(
            "Пошук сервера в діапазоні "
            "192.168.0.160-165..."
        )

        for i in range(160, 165):

            ip = f"{BASE_IP}{i}"

            available, url = (
                await check_server_available(
                    session,
                    ip
                )
            )

            if available:

                print(
                    f"Знайдено сервер: {url}"
                )

                return url

    return None


def get_user_ip():
    """
    Запитує у користувача IP-адресу.
    """

    while True:

        try:

            user_input = input(
                "Введіть останнє число IP-адреси "
                "(наприклад, 111 або 165): "
            )

            last_octet = int(user_input)

            if 1 <= last_octet <= 254:

                url = (
                    f"http://{BASE_IP}{last_octet}:"
                    f"{DEFAULT_PORT}/get?accX&accY&accZ"
                )

                print(
                    f"Використовується адреса: {url}"
                )

                return url

            print(
                "Число має бути в діапазоні "
                "від 1 до 254."
            )

        except ValueError:

            print(
                "Будь ласка, введіть коректне число."
            )


async def register_client(websocket):
    """
    Реєструє WebSocket-клієнта.
    """

    CONNECTED_CLIENTS.add(websocket)

    print(
        f"Новий клієнт підключився. "
        f"Всього клієнтів: "
        f"{len(CONNECTED_CLIENTS)}"
    )

    try:

        await websocket.wait_closed()

    finally:

        CONNECTED_CLIENTS.remove(websocket)

        print(
            f"Клієнт від'єднався. "
            f"Всього клієнтів: "
            f"{len(CONNECTED_CLIENTS)}"
        )


async def data_loop(
    osc_sender=None,
    run_threshold=1.5,
    move_threshold=0.5
):
    """
    Головний цикл отримання даних смартфона.
    """

    global calibration_state
    global calibration_values
    global calibration_data
    global filtered_accX
    global filtered_accY
    global filtered_accZ

    global smart_calibration_state
    global smart_calibration_data

    async with aiohttp.ClientSession() as session:

        while True:

            try:

                async with session.get(
                    HTTP_SERVER_URL
                ) as response:

                    if response.status == 200:

                        data = await response.json()

                        raw_accX = (
                            data.get("buffer", {})
                            .get("accX", {})
                            .get("buffer", [0])[0]
                        )

                        raw_accY = (
                            data.get("buffer", {})
                            .get("accY", {})
                            .get("buffer", [0])[0]
                        )

                        raw_accZ = (
                            data.get("buffer", {})
                            .get("accZ", {})
                            .get("buffer", [0])[0]
                        )

                        accX = raw_accX
                        accY = raw_accY
                        accZ = raw_accZ

                        # Smart calibration

                        current_smart_state = (
                            smart_calibration_state.get()
                        )

                        if (
                            current_smart_state
                            != SmartCalibrationState.IDLE
                            and current_smart_state
                            != SmartCalibrationState.DONE
                        ):

                            if current_smart_state == (
                                SmartCalibrationState
                                .COLLECTING_NEUTRAL
                            ):

                                smart_calibration_data[
                                    "neutral"
                                ].append(
                                    (accX, accY, accZ)
                                )

                            elif current_smart_state == (
                                SmartCalibrationState
                                .COLLECTING_FORWARD
                            ):

                                smart_calibration_data[
                                    "forward"
                                ].append(
                                    (accX, accY, accZ)
                                )

                            elif current_smart_state == (
                                SmartCalibrationState
                                .COLLECTING_BACKWARD
                            ):

                                smart_calibration_data[
                                    "backward"
                                ].append(
                                    (accX, accY, accZ)
                                )

                            elif current_smart_state == (
                                SmartCalibrationState
                                .COLLECTING_LEFT
                            ):

                                smart_calibration_data[
                                    "left"
                                ].append(
                                    (accX, accY, accZ)
                                )

                            elif current_smart_state == (
                                SmartCalibrationState
                                .COLLECTING_RIGHT
                            ):

                                smart_calibration_data[
                                    "right"
                                ].append(
                                    (accX, accY, accZ)
                                )

                            continue

                        # Звичайне калібрування

                        if (
                            calibration_state
                            == CalibrationState.CALIBRATING
                        ):

                            calibration_data.append(
                                (accX, accY, accZ)
                            )

                            continue

                        if (
                            calibration_state
                            == CalibrationState.DONE
                        ):

                            accX -= calibration_values[
                                "delta_accX"
                            ]

                            accY -= calibration_values[
                                "delta_accY"
                            ]

                            accZ -= calibration_values[
                                "delta_accZ"
                            ]

                        # OSC

                        if osc_sender:

                            osc_sender.send_commands(
                                raw_accX,
                                raw_accY,
                                raw_accZ,
                                calibration_values[
                                    "delta_accX"
                                ],
                                calibration_values[
                                    "delta_accY"
                                ],
                                calibration_values[
                                    "delta_accZ"
                                ],
                                run_threshold=run_threshold,
                                move_threshold=move_threshold
                            )

                        # EMA filter

                        filtered_accX = (
                            ALPHA * accX
                            + (1 - ALPHA)
                            * filtered_accX
                        )

                        filtered_accY = (
                            ALPHA * accY
                            + (1 - ALPHA)
                            * filtered_accY
                        )

                        filtered_accZ = (
                            ALPHA * accZ
                            + (1 - ALPHA)
                            * filtered_accZ
                        )

                        ratio_x = clamp(
                            filtered_accX
                            / SCALING_FACTOR,
                            -1.0,
                            1.0
                        )

                        ratio_y = clamp(
                            filtered_accY
                            / SCALING_FACTOR,
                            -1.0,
                            1.0
                        )

                        angle_x = math.degrees(
                            math.asin(ratio_x)
                        )

                        angle_y = math.degrees(
                            math.asin(ratio_y)
                        )

                        SENSOR_DATA.update({
                            "accX": filtered_accX,
                            "accY": filtered_accY,
                            "accZ": filtered_accZ,
                            "angle_x": angle_x,
                            "angle_y": angle_y
                        })

                    else:

                        print(
                            f"Помилка отримання даних: "
                            f"HTTP {response.status}"
                        )

            except aiohttp.ClientError as e:

                print(
                    f"Помилка підключення "
                    f"до HTTP-сервера: {e}"
                )

            except json.JSONDecodeError:

                print(
                    "Помилка: не вдалося "
                    "розкодувати JSON."
                )

            # WebSocket

            if CONNECTED_CLIENTS:

                message = json.dumps({
                    "accX": SENSOR_DATA["accX"],
                    "accY": SENSOR_DATA["accY"],
                    "accZ": SENSOR_DATA["accZ"],
                    "angle_x": SENSOR_DATA["angle_x"],
                    "angle_y": SENSOR_DATA["angle_y"]
                })

                await asyncio.gather(
                    *[
                        client.send(message)
                        for client in CONNECTED_CLIENTS
                    ],
                    return_exceptions=True
                )

            await asyncio.sleep(0.05)


def calibration_thread(config):
    """
    Потік для звичайного калібрування.
    """

    global calibration_state
    global calibration_values
    global calibration_data

    print(
        "Режим калібрування. "
        "Тримайте смартфон у стані спокою "
        "впродовж 5 секунд"
    )

    calibration_data = []

    calibration_state = (
        CalibrationState.CALIBRATING
    )

    for i in range(3, -1, -1):

        if i == 0:

            print(f"{i} .......")

            winsound.Beep(1000, 700)

        else:

            print(f"{i} ...")

            winsound.Beep(1000, 200)

        time.sleep(1)

    if calibration_data:

        accX_data, accY_data, accZ_data = zip(
            *calibration_data
        )

        calibration_values["delta_accX"] = (
            np.mean(accX_data)
        )

        calibration_values["delta_accY"] = (
            np.mean(accY_data)
        )

        calibration_values["delta_accZ"] = (
            np.mean(accZ_data)
        )

        print(
            "Калібрування завершено: "
            f"delta_accX="
            f"{calibration_values['delta_accX']:.2f}, "
            f"delta_accY="
            f"{calibration_values['delta_accY']:.2f}, "
            f"delta_accZ="
            f"{calibration_values['delta_accZ']:.2f}"
        )

        config["calibration"] = calibration_values

        save_config(config)

    else:

        print(
            "Не вдалося отримати дані "
            "для калібрування."
        )

    calibration_state = (
        CalibrationState.DONE
    )


def smart_calibration_thread(
    config,
    osc_sender,
    lock
):
    """
    Потік для розумного калібрування.
    """

    try:

        global smart_calibration_state
        global smart_calibration_data
        global keyboard_input_suspended
        global calibration_values

        if not SmartCalibration:

            print(
                "Модуль SmartCalibration "
                "не завантажено."
            )

            return

        data_collector = DataCollector(
            smart_calibration_data,
            smart_calibration_state,
            SmartCalibrationState
        )

        calibrator = SmartCalibration(
            data_collector
        )

        recommendations = (
            calibrator.run_calibration()
        )

        if (
            recommendations
            and recommendations.get("bindings")
        ):

            new_bindings = (
                recommendations["bindings"]
            )

            new_calibration = (
                recommendations.get(
                    "calibration",
                    {}
                )
            )

            while True:

                keyboard_input_suspended.set()

                answer = input(
                    "Зберегти нові налаштування? "
                    "(y/n): "
                ).lower()

                keyboard_input_suspended.clear()

                if answer in ["y", "yes"]:

                    config["osc_bindings"] = (
                        new_bindings
                    )

                    if new_calibration:

                        config["calibration"] = (
                            new_calibration
                        )

                        calibration_values.update(
                            new_calibration
                        )

                    save_config(config)

                    if osc_sender:

                        osc_sender.update_bindings(
                            new_bindings
                        )

                    print(
                        "Налаштування оновлено."
                    )

                    break

                elif answer in ["n", "no"]:

                    print(
                        "Зміни скасовано."
                    )

                    break

            print(
                "Клавіші керування: "
                "F1 - калібрування стану спокою, "
                "F2 - розумне калібрування, "
                "Esc - завершення роботи"
            )

    finally:

        lock.release()


def input_handler(
    config,
    osc_sender=None
):
    """
    Обробник клавіатури.
    """

    global calibration_state
    global smart_calibration_state
    global keyboard_input_suspended

    while True:

        if keyboard_input_suspended.is_set():

            time.sleep(0.1)

            continue

        try:

            key = keyboard.read_key()

            if key == "f1" or key == "F1":

                if (
                    calibration_state
                    != CalibrationState.CALIBRATING
                    and
                    smart_calibration_state.get()
                    == SmartCalibrationState.IDLE
                ):

                    cal_thread = threading.Thread(
                        target=calibration_thread,
                        args=(config,)
                    )

                    cal_thread.start()

            elif key == "f2" or key == "F2":

                if smart_cal_lock.acquire(
                    blocking=False
                ):

                    if (
                        calibration_state
                        == CalibrationState.CALIBRATING
                        or
                        smart_calibration_state.get()
                        != SmartCalibrationState.IDLE
                    ):

                        smart_cal_lock.release()

                    else:

                        smart_cal_thread = (
                            threading.Thread(
                                target=smart_calibration_thread,
                                args=(
                                    config,
                                    osc_sender,
                                    smart_cal_lock
                                )
                            )
                        )

                        smart_cal_thread.start()

            elif key == "esc":

                print("Завершення роботи...")

                os.kill(
                    os.getpid(),
                    signal.SIGINT
                )

                break

        except Exception:

            time.sleep(0.1)


async def main_async(
    osc_sender=None,
    use_websocket=False,
    run_threshold=1.5,
    move_threshold=0.5,
    config=None
):
    """
    Основна асинхронна функція.
    """

    global HTTP_SERVER_URL
    global calibration_values
    global calibration_state

    saved_ip = config.get("server_ip")

    # Завантаження калібрування

    if "calibration" in config:

        calibration_values["delta_accX"] = (
            config["calibration"].get(
                "delta_accX",
                0.0
            )
        )

        calibration_values["delta_accY"] = (
            config["calibration"].get(
                "delta_accY",
                0.0
            )
        )

        calibration_values["delta_accZ"] = (
            config["calibration"].get(
                "delta_accZ",
                0.0
            )
        )

        if any(calibration_values.values()):

            calibration_state = (
                CalibrationState.DONE
            )

            print(
                "Завантажено збережене калібрування: "
                f"delta_accX="
                f"{calibration_values['delta_accX']:.2f}, "
                f"delta_accY="
                f"{calibration_values['delta_accY']:.2f}, "
                f"delta_accZ="
                f"{calibration_values['delta_accZ']:.2f}"
            )

    server_url = None

    # Перевірка збереженої адреси

    if saved_ip:

        print(
            f"Перевірка збереженої адреси: "
            f"{saved_ip}..."
        )

        async with aiohttp.ClientSession() as session:

            available, url = (
                await check_server_available(
                    session,
                    saved_ip
                )
            )

            if available:

                print(
                    f"Знайдено сервер "
                    f"за збереженою адресою: {url}"
                )

                server_url = url

            else:

                print(
                    "Збережена адреса недоступна. "
                    "Пошук нового сервера..."
                )

    # Пошук сервера

    if server_url is None:

        server_url = await find_server()

    # Ручне введення

    if server_url is None:

        print(
            "\nНе вдалося знайти сервер "
            "у заданих діапазонах."
        )

        print(
            "Будь ласка, введіть "
            "адресу сервера вручну."
        )

        server_url = get_user_ip()

    ip_to_save = (
        server_url.split("//")[1]
        .split(":")[0]
    )

    config["server_ip"] = ip_to_save

    save_config(config)

    HTTP_SERVER_URL = server_url

    print(
        f"Підключення до сервера: "
        f"{HTTP_SERVER_URL}"
    )

    server = None

    if use_websocket:

        server = await websockets.serve(
            register_client,
            "localhost",
            8767
        )

        print(
            "WebSocket-сервер запущено "
            "на ws://localhost:8767"
        )

    else:

        print(
            "WebSocket-сервер не запущено "
            "(використовуйте --websocket "
            "для активації)."
        )

    print(
        "Клавіші керування: "
        "F1 - калібрування стану спокою, "
        "F2 - розумне калібрування, "
        "Esc - завершення роботи"
    )

    data_task = asyncio.create_task(
        data_loop(
            osc_sender=osc_sender,
            run_threshold=run_threshold,
            move_threshold=move_threshold
        )
    )

    try:

        await data_task

    except asyncio.CancelledError:

        pass

    finally:

        if server:

            server.close()

            await server.wait_closed()


def main():
    """
    Точка запуску програми.

    Tkinter працює у головному потоці.
    asyncio та keyboard input працюють
    у фонових потоках.
    """

    config = load_config()

    debug_mode = config.get(
        "debug",
        False
    )

    thresholds = config.get(
        "thresholds",
        {}
    )

    run_threshold_deg = thresholds.get(
        "run",
        20.0
    )

    move_threshold_deg = thresholds.get(
        "move",
        5.0
    )

    run_threshold = degrees_to_accel(
        run_threshold_deg
    )

    move_threshold = degrees_to_accel(
        move_threshold_deg
    )

    startup_mode = config.get(
        "startup_mode",
        {}
    )

    parser = argparse.ArgumentParser(
        description=(
            "WebSocket-сервер для "
            "трансляції даних "
            "з акселерометра."
        )
    )

    parser.add_argument(
        "--osc",
        action="store_true",
        help=(
            "Активувати режим "
            "надсилання OSC команд "
            "(перевизначає конфігурацію)."
        )
    )

    parser.add_argument(
        "--websocket",
        action="store_true",
        help=(
            "Активувати WebSocket сервер "
            "(перевизначає конфігурацію)."
        )
    )

    args = parser.parse_args()

    use_osc = (
        args.osc
        or startup_mode.get(
            "osc",
            False
        )
    )

    use_websocket = (
        args.websocket
        or startup_mode.get(
            "websocket",
            False
        )
    )

    # -------------------------------------------------
    # Перевірка GUI
    # -------------------------------------------------

    if CommandGUI is None:

        print(
            "GUI неможливо запустити: "
            "не вдалося імпортувати "
            "command_gui."
        )

        return

    command_gui = CommandGUI()

    # -------------------------------------------------
    # OSC
    # -------------------------------------------------

    if use_osc and OSCCommands is None:

        print(
            "Режим OSC неможливий, "
            "оскільки не вдалося "
            "імпортувати OSCCommands."
        )

        return

    osc_sender = None

    if use_osc:

        osc_bindings = config.get(
            "osc_bindings",
            []
        )

        osc_sender = OSCCommands(
            debug=debug_mode,
            osc_bindings=osc_bindings,
            on_command_change=(
                command_gui.update_command
            )
        )

    # -------------------------------------------------
    # Keyboard input thread
    # -------------------------------------------------

    input_thread = threading.Thread(
        target=input_handler,
        args=(config, osc_sender),
        daemon=True
    )

    input_thread.start()

    # -------------------------------------------------
    # Asyncio thread
    # -------------------------------------------------

    def run_asyncio():

        try:

            asyncio.run(
                main_async(
                    osc_sender=osc_sender,
                    use_websocket=use_websocket,
                    run_threshold=run_threshold,
                    move_threshold=move_threshold,
                    config=config
                )
            )

        except KeyboardInterrupt:

            pass

    asyncio_thread = threading.Thread(
        target=run_asyncio,
        daemon=True
    )

    asyncio_thread.start()

    # -------------------------------------------------
    # Tkinter main loop
    # -------------------------------------------------

    try:

        command_gui.run()

    finally:

        if osc_sender:

            osc_sender.release_all_commands()


if __name__ == "__main__":
    main()
    