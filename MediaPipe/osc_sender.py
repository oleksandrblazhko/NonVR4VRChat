"""
osc_sender.py

Передача OSC-команд до VRChat.

Кожну надіслану команду можна виводити у консоль разом із значенням —
для цього в `config.json` має стояти `debug: true` (див.
`load_debug_flag`).

Автор: OpenAI
"""

from __future__ import annotations

import json
import os

from pythonosc import udp_client


# ============================================================
# Parameters
# ============================================================

CONFIG_FILE = "config.json"

# Безперервні осі надсилаються на кожному кадрі, тому у консоль виводиться
# лише зміна значення щонайменше на цей крок — інакше вивід затопить
# тридцятьма рядками за секунду.
DEBUG_VALUE_STEP = 0.01


# ============================================================
# Debug
# ============================================================

def load_debug_flag() -> bool:
    """
    Ознака `debug` з config.json.

    Без файлу, без ключа або в пошкодженому файлі — вимкнено.
    """

    path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)

    try:

        with open(path, "r", encoding="utf-8") as f:

            return bool(json.load(f).get("debug", False))

    except Exception as e:

        print(f"Error loading {CONFIG_FILE}: {e}. Debug output disabled.")

        return False


# ============================================================
# OSCSender
# ============================================================

class OSCSender:
    """
    Передача OSC-команд до VRChat.
    """

    # --------------------------------------------------------

    def __init__(
            self,
            ip: str = "127.0.0.1",
            port: int = 9000,
            debug=None
    ):

        self.ip = ip
        self.port = port

        # None — взяти з config.json, інакше — явне значення викликача.
        self.debug = load_debug_flag() if debug is None else bool(debug)

        self._last_debug_values = {}

        self.client = udp_client.SimpleUDPClient(
            self.ip,
            self.port
        )

    # --------------------------------------------------------

    def _debug_message(self, address: str, value):
        """
        Відладочне повідомлення про надіслану команду.

        Логічні команди (хоп/розтиснення) — це події, тому друкуються
        завжди. Речові осі друкуються лише коли значення змінилось хоча б
        на `DEBUG_VALUE_STEP` від попереднього виводу.
        """

        if not self.debug:

            return

        if isinstance(value, bool):

            print(f"OSC: {address} = {value}")

            return

        last = self._last_debug_values.get(address)

        if last is not None and abs(value - last) < DEBUG_VALUE_STEP:

            return

        self._last_debug_values[address] = value

        print(f"OSC: {address} = {value:.3f}")

    # --------------------------------------------------------

    def send_look(
            self,
            horizontal: float,
            vertical: float
    ):
        """
        Передача команд керування поглядом.
        """

        horizontal = max(-1.0, min(1.0, horizontal))
        vertical = max(-1.0, min(1.0, vertical))

        self.client.send_message(
            "/input/LookHorizontal",
            float(horizontal)
        )

        self.client.send_message(
            "/input/LookVertical",
            float(vertical)
        )

        self._debug_message(
            "/input/LookHorizontal",
            horizontal
        )

        self._debug_message(
            "/input/LookVertical",
            vertical
        )

    # --------------------------------------------------------

    def send_horizontal(
            self,
            value: float
    ):
        """
        Передати лише горизонтальний поворот.
        """

        value = max(-1.0, min(1.0, value))

        self.client.send_message(
            "/input/LookHorizontal",
            float(value)
        )

        self._debug_message(
            "/input/LookHorizontal",
            value
        )

    # --------------------------------------------------------

    def send_vertical(
            self,
            value: float
    ):
        """
        Передати лише вертикальний поворот.
        """

        value = max(-1.0, min(1.0, value))

        self.client.send_message(
            "/input/LookVertical",
            float(value)
        )

        self._debug_message(
            "/input/LookVertical",
            value
        )

    # --------------------------------------------------------

    def send_grab_right(self, value: bool):
        """
        Send GrabRight command.
        """
        self.client.send_message(
            "/input/GrabRight",
            value
        )

        self._debug_message("/input/GrabRight", value)

    def send_drop_right(self, value: bool):
        """
        Send DropRight command.
        """
        self.client.send_message(
            "/input/DropRight",
            value
        )

        self._debug_message("/input/DropRight", value)

    # --------------------------------------------------------

    def send_use_right(self, value: bool):
        """
        Send UseRight command.

        Дія предмета, на який наведено погляд.
        """
        self.client.send_message(
            "/input/UseRight",
            value
        )

        self._debug_message("/input/UseRight", value)

    # --------------------------------------------------------

    def center(self):
        """
        Повернути погляд у центральне положення.
        """

        self.send_look(0.0, 0.0)

    # --------------------------------------------------------

    def close(self):
        """
        Завершення роботи.

        Зараз спеціальних дій не потрібно,
        метод залишений для сумісності.
        """

        pass


# ============================================================
# Перевірка
# ============================================================

if __name__ == "__main__":

    sender = OSCSender()

    print("OSC test")

    sender.send_look(0.5, 0.0)
    print("LookHorizontal = 0.5")

    input("Enter...")

    sender.send_look(-0.5, 0.0)
    print("LookHorizontal = -0.5")

    input("Enter...")

    sender.send_look(0.0, 0.5)
    print("LookVertical = 0.5")

    input("Enter...")

    sender.center()

    print("Center")
