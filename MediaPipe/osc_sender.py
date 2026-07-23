"""
osc_sender.py

Передача OSC-команд до VRChat.

Автор: OpenAI
"""

from __future__ import annotations

from pythonosc import udp_client


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
            port: int = 9000
    ):

        self.ip = ip
        self.port = port

        self.client = udp_client.SimpleUDPClient(
            self.ip,
            self.port
        )

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
        
        # if horizontal > 0.5 or horizontal < -0.5:
        #     print(f"OSC LookHorizontal={horizontal:.3f}")
        #if horizontal > 0.1:
        #   print(f"OSC LookVertical={vertical:.3f}")   

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

    # --------------------------------------------------------

    def send_grab_right(self, value: bool):
        """
        Send GrabRight command.
        """
        self.client.send_message(
            "/input/GrabRight",
            value
        )

    def send_drop_right(self, value: bool):
        """
        Send DropRight command.
        """
        self.client.send_message(
            "/input/DropRight",
            value
        )

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
