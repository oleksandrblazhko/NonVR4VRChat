"""
status_beacon.py

«Пульс» програми MediaPipe для лаунчера (VRChatApp).

Раз на секунду надсилає на localhost невеликий UDP-пакет (JSON):

    {"ts": <час>, "pid": <PID>, "pose": <поза видна>, "calibrated": <є калібрування>}

Лаунчер приймає його на порту BEACON_PORT і за ним показує індикатор
«Камера». Якщо пульс не приходить кілька секунд (програма закрита або
зависла), індикатор стає червоним. UDP на localhost не залежить ні від
прав доступу до файлів, ні від тимчасових папок, ні від того, чи запущено
лаунчер від імені адміністратора.

Порт має збігатися з BEACON_PORT у VRChatApp/status.py.
Будь-які помилки відправки ігноруються: індикатор не повинен ламати керування.
"""

from __future__ import annotations

import json
import os
import socket
import time


BEACON_PORT = 9002


class StatusBeacon:

    def __init__(self, port: int = BEACON_PORT, interval: float = 1.0):
        self.address = ("127.0.0.1", port)
        self.interval = interval
        self._last_send = 0.0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _send(self, data: dict):
        try:
            self._sock.sendto(json.dumps(data).encode("utf-8"), self.address)
        except OSError:
            pass

    def update(self, pose_detected: bool, calibrated: bool):
        """Викликається на кожному кадрі; сама шле не частіше за interval."""

        now = time.time()

        if now - self._last_send < self.interval:
            return

        self._last_send = now

        self._send({
            "ts": now,
            "pid": os.getpid(),
            "pose": bool(pose_detected),
            "calibrated": bool(calibrated),
        })

    def clear(self):
        """Повідомити лаунчер, що програма закрилась (при нормальному виході)."""

        self._send({"closed": True})

        try:
            self._sock.close()
        except OSError:
            pass