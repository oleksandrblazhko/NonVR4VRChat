"""
status.py

Фоновий моніторинг стану системи для лаунчера.

Слідкує за чотирма речами:

    vrchat  - чи запущено процес VRChat.exe
    camera  - чи працює програма MediaPipe (через «пульс» status_beacon по UDP)
    phone   - чи відповідає phyphox на смартфоні та чи йдуть дані
    osc     - чи надсилає VRChat OSC-повідомлення (слухаємо UDP-порт 9001)

Кожен пункт має рівень (Status.level):

    ok      - зелений, усе працює
    wait    - жовтий, процес іде (запуск, очікування)
    off     - червоний, не працює
    unknown - сірий, перевірити не вдалося

та, за потреби, підказку (Status.hint) - що саме робити.

Монітор працює у двох фонових потоках і нічого не малює: GUI лише
періодично читає snapshot(). Зміни стану потрапляють у журнал через
колбек log(text, level).

Про OSC. VRChat приймає команди на порту 9000 по UDP без підтвердження,
тому напряму дізнатись, чи ввімкнено OSC, неможливо. Але коли OSC
ввімкнено, сам VRChat надсилає повідомлення на порт 9001 (зміна аватара,
параметри). Їх наявність і є ознакою, що OSC працює. Якщо порт 9001 зайнятий
іншою програмою, статус буде «unknown», а не хибна помилка.
"""

from __future__ import annotations

import json
import os
import select
import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


# ============================================================
# Рівні статусу
# ============================================================

OK = "ok"
WAIT = "wait"
OFF = "off"
UNKNOWN = "unknown"

KEYS = ("vrchat", "camera", "phone", "osc")

# Порядок, у якому підказки показуються під рядком індикаторів.
HINT_ORDER = ("osc", "phone", "camera", "vrchat")

# Назви для журналу
LOG_NAMES = {
    "vrchat": "VRChat",
    "camera": "Камера",
    "phone": "Телефон",
    "osc": "OSC",
}

# Порт, на який MediaPipe/status_beacon.py шле «пульс» камери (UDP, localhost).
BEACON_PORT = 9002

VRCHAT_PROCESS = "VRChat.exe"
OSC_PORT_FROM_VRCHAT = 9001
PHYPHOX_PORT = 8080


@dataclass(frozen=True)
class Status:
    level: str = UNKNOWN
    text: str = "перевірка..."
    hint: str = ""


# ============================================================
# Допоміжні перевірки
# ============================================================

def is_process_running(name: str) -> bool:
    """Чи є у системі процес із такою назвою."""

    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=5,
                # без мигання консольного вікна
                creationflags=0x08000000,
            )
            # У CSV-виводі ім'я процесу в лапках; повідомлення
            # «завдань не знайдено» його не містить у жодній локалі.
            return f'"{name.lower()}"' in result.stdout.lower()

        result = subprocess.run(
            ["pgrep", "-f", name],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0

    except Exception:
        return False


def read_phone_ip(config_path: Path) -> str:
    """IP-адреса телефону з SmartPhone/config.json."""

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return str(json.load(f).get("server_ip", "")).strip()
    except Exception:
        return ""


def probe_phyphox(ip: str, port: int = PHYPHOX_PORT, timeout: float = 2.0):
    """
    Опитує phyphox так само, як SmartPhone/main.py.

    Повертає:
        "ok"        - сервер відповідає і віддає значення акселерометра;
        "no_data"   - сервер відповідає, але вимірювання не запущено;
        "no_server" - сервер недоступний.
    """

    url = f"http://{ip}:{port}/get?accX&accY&accZ"

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                return "no_server"
            data = json.loads(response.read().decode("utf-8"))

    except Exception:
        return "no_server"

    buffers = data.get("buffer", {})

    for axis in ("accX", "accY", "accZ"):
        values = buffers.get(axis, {}).get("buffer", [None])
        if not values or values[0] is None:
            return "no_data"

    return "ok"


# ============================================================
# Монітор
# ============================================================

class StatusMonitor:

    # Скільки чекати OSC-повідомлень від запущеного VRChat,
    # перш ніж вважати, що OSC вимкнено.
    OSC_WAIT_SECONDS = 60.0

    # Скільки чекати «пульс» камери після запуску MediaPipe
    # (імпорт бібліотек + відкриття камери).
    CAMERA_START_SECONDS = 15.0

    # Пульс старший за цей вік вважається згаслим.
    BEACON_MAX_AGE = 3.0

    # Через скільки секунд без пози з'являється підказка.
    POSE_HINT_AFTER = 8.0

    def __init__(
        self,
        log=None,
        phone_config_path: Path | None = None,
        osc_port: int = OSC_PORT_FROM_VRCHAT,
        phyphox_port: int = PHYPHOX_PORT,
        beacon_port: int = BEACON_PORT,
        process_check=is_process_running,
        assume_launched=(),
    ):
        self._log = log or (lambda text, level="info": None)
        self._phone_config_path = phone_config_path
        self._osc_port = osc_port
        self._phyphox_port = phyphox_port
        self._beacon_port = beacon_port
        self._process_check = process_check

        self._lock = threading.Lock()
        self._statuses = {key: Status() for key in KEYS}

        self._stop = threading.Event()
        self._threads = []

        # Які програми запущено і коли (для підказок). Якщо їх запускає не
        # лаунчер, а, наприклад, start.bat, ключі передаються в
        # assume_launched: монітор вважає їх запущеними з моменту старту.
        self._launched = {key: time.time() for key in assume_launched}

        # Стан VRChat / OSC.
        self._sock = None
        self._next_bind_try = 0.0

        # UDP-сокет, на який MediaPipe надсилає «пульс» камери.
        self._beacon_sock = None
        self._next_beacon_try = 0.0
        self._beacon_data = None
        self._beacon_time = 0.0
        self._vrchat_since = None
        self._osc_seen = False

        # Стан камери.
        self._pose_missing_since = None

    # --------------------------------------------------------
    # Керування
    # --------------------------------------------------------

    def start(self):
        for target in (self._fast_loop, self._phone_loop):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self):
        self._stop.set()

        for thread in self._threads:
            thread.join(timeout=3)

        for name in ("_sock", "_beacon_sock"):
            sock = getattr(self, name)
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
                setattr(self, name, None)

    def note_launch(self, key: str):
        """Лаунчер запустив програму (camera або phone)."""
        with self._lock:
            self._launched[key] = time.time()

    def note_exit(self, key: str):
        """Програма, запущена лаунчером, завершилась."""
        with self._lock:
            self._launched.pop(key, None)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._statuses)

    def hints(self) -> list:
        snap = self.snapshot()
        return [
            snap[key].hint
            for key in HINT_ORDER
            if snap[key].hint
        ]

    # --------------------------------------------------------
    # Запис статусу + журнал
    # --------------------------------------------------------

    def _set(self, key: str, status: Status):
        with self._lock:
            previous = self._statuses[key]
            self._statuses[key] = status

        if status.level != previous.level or status.text != previous.text:
            level = "info" if status.level in (OK, WAIT) else "warn"
            self._log(f"{LOG_NAMES[key]}: {status.text}", level)

        if status.hint and status.hint != previous.hint:
            self._log(status.hint, "warn")

    # --------------------------------------------------------
    # Швидкий цикл: VRChat, OSC, камера
    # --------------------------------------------------------

    def _fast_loop(self):
        while not self._stop.is_set():
            self._ensure_sockets()
            self._drain(0.5)

            now = time.time()
            vrchat_running = self._process_check(VRCHAT_PROCESS)

            self._update_vrchat(vrchat_running, now)
            self._update_osc(vrchat_running, now)
            self._update_camera(now)

    @staticmethod
    def _bind_udp(port: int):
        """UDP-сокет на localhost або None, якщо порт зайнятий."""

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            # SO_REUSEADDR навмисно не ставимо: якщо порт зайнятий,
            # треба чесно сказати «не вдалося перевірити».
            sock.bind(("127.0.0.1", port))
            return sock
        except OSError:
            sock.close()
            return None

    def _ensure_sockets(self):
        now = time.time()

        if self._sock is None and now >= self._next_bind_try:
            self._sock = self._bind_udp(self._osc_port)
            if self._sock is None:
                self._next_bind_try = now + 5.0

        if self._beacon_sock is None and now >= self._next_beacon_try:
            self._beacon_sock = self._bind_udp(self._beacon_port)
            if self._beacon_sock is None:
                self._next_beacon_try = now + 5.0

    def _drain(self, duration: float):
        """Слухає обидва порти: OSC від VRChat і «пульс» від MediaPipe."""

        end = time.time() + duration

        while not self._stop.is_set():
            remaining = end - time.time()

            if remaining <= 0:
                break

            socks = [
                s for s in (self._sock, self._beacon_sock) if s is not None
            ]

            if not socks:
                self._stop.wait(remaining)
                break

            try:
                readable, _, _ = select.select(socks, [], [], remaining)
            except (OSError, ValueError):
                break

            for sock in readable:
                try:
                    data, _ = sock.recvfrom(65535)
                except OSError:
                    continue

                if sock is self._sock:
                    self._osc_seen = True
                else:
                    self._on_beacon(data)

    def _on_beacon(self, data: bytes):
        try:
            parsed = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return

        if isinstance(parsed, dict):
            self._beacon_data = parsed
            self._beacon_time = time.time()

    def _update_vrchat(self, running: bool, now: float):
        if not running:
            self._vrchat_since = None
            self._osc_seen = False
            self._set("vrchat", Status(OFF, "вимкнено"))
            return

        if self._vrchat_since is None:
            self._vrchat_since = now

        starting = (
            not self._osc_seen
            and now - self._vrchat_since < self.OSC_WAIT_SECONDS
        )

        if starting:
            self._set("vrchat", Status(WAIT, "запускається"))
        else:
            self._set("vrchat", Status(OK, "працює"))

    def _update_osc(self, vrchat_running: bool, now: float):
        if not vrchat_running:
            self._set("osc", Status(OFF, "чекає на VRChat"))
            return

        if self._sock is None:
            self._set("osc", Status(
                UNKNOWN,
                "не перевірено",
                f"Порт {self._osc_port} зайнятий іншою програмою, тому "
                "перевірити OSC не вдалося.",
            ))
            return

        if self._osc_seen:
            self._set("osc", Status(OK, "працює"))
            return

        if now - self._vrchat_since < self.OSC_WAIT_SECONDS:
            self._set("osc", Status(WAIT, "очікування входу у світ"))
            return

        self._set("osc", Status(
            OFF,
            "сигналу немає",
            "VRChat не надсилає OSC-повідомлень. Увімкніть: Action Menu → "
            "Options → OSC → Enabled (за потреби перезайдіть у світ).",
        ))

    def _read_beacon(self, now: float):
        """Свіжий «пульс» MediaPipe або None."""

        data = self._beacon_data

        if data is None or data.get("closed"):
            return None

        if now - self._beacon_time <= self.BEACON_MAX_AGE:
            return data

        return None

    def _update_camera(self, now: float):
        beacon = self._read_beacon(now)

        if beacon is not None:
            self._update_camera_running(beacon, now)
            return

        self._pose_missing_since = None

        # MediaPipe сам повідомив, що закрився (ESC): це не помилка.
        if self._beacon_data is not None and self._beacon_data.get("closed"):
            self._set("camera", Status(OFF, "закрито"))
            return

        with self._lock:
            launched_at = self._launched.get("camera")

        if launched_at is None:
            self._set("camera", Status(OFF, "не запущено"))
        elif now - launched_at < self.CAMERA_START_SECONDS:
            self._set("camera", Status(WAIT, "запускається"))
        else:
            if self._beacon_sock is None:
                hint = (
                    f"Порт {self._beacon_port} зайнятий іншою програмою "
                    "(можливо, відкрито другий лаунчер), тому сигнал камери "
                    "не приймається."
                )
            else:
                hint = (
                    "Лаунчер не отримує сигнал від MediaPipe. Якщо вікно "
                    "камери відкрите, у консолі MediaPipe має бути рядок "
                    "«Status beacon: ON»: якщо його немає, оновіть "
                    "MediaPipe/main.py і status_beacon.py та перезапустіть "
                    "start.bat. Якщо вікна камери немає, перевірте "
                    "camera_index у MediaPipe/config.json і чи не зайняла "
                    "камеру інша програма."
                )

            self._set("camera", Status(OFF, "немає сигналу", hint))

    def _update_camera_running(self, beacon: dict, now: float):
        if not beacon.get("pose"):
            if self._pose_missing_since is None:
                self._pose_missing_since = now

            hint = ""
            if now - self._pose_missing_since > self.POSE_HINT_AFTER:
                hint = ("Станьте в кадр так, щоб було видно ніс і плечі, "
                        "і перевірте освітлення.")

            self._set("camera", Status(WAIT, "поза не виявлена", hint))
            return

        self._pose_missing_since = None

        if not beacon.get("calibrated"):
            self._set("camera", Status(
                WAIT,
                "потрібне калібрування",
                "Натисніть 1 у вікні камери й постійте нерухомо 4 секунди.",
            ))
            return

        self._set("camera", Status(OK, "працює"))

    # --------------------------------------------------------
    # Повільний цикл: телефон (запит може чекати до 2 с)
    # --------------------------------------------------------

    def _phone_loop(self):
        while not self._stop.is_set():
            self._update_phone()
            self._stop.wait(2.0)

    def _update_phone(self):
        ip = (
            read_phone_ip(self._phone_config_path)
            if self._phone_config_path else ""
        )

        with self._lock:
            phone_launched = "phone" in self._launched

        if not ip:
            self._set("phone", Status(
                OFF,
                "IP не задано",
                "Вкажіть IP-адресу телефону: server_ip у SmartPhone/config.json.",
            ))
            return

        result = probe_phyphox(ip, self._phyphox_port)

        if result == "ok":
            self._set("phone", Status(OK, "підключено"))

        elif result == "no_data":
            self._set("phone", Status(
                WAIT,
                "вимірювання не запущено",
                "У phyphox натисніть ▶ (трикутник), щоб запустити "
                "акселерометр.",
            ))

        else:
            hint = ""
            if phone_launched:
                hint = (
                    f"Телефон {ip} не відповідає. Перевірте, що phyphox "
                    "запущено, увімкнено Allow remote access і телефон у "
                    "тій самій Wi-Fi мережі."
                )
            self._set("phone", Status(OFF, "немає зв'язку", hint))