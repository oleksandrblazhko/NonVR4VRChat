"""
camera_reader.py

Окремий потік для захоплення кадрів з камери.
У пам'яті завжди зберігається лише останній кадр.

Номер камери береться з `config.json` (ключ `camera_index`), якщо
викликач не передав його явно в конструктор.
"""

import json
import os
import threading
import time

import cv2


# ============================================================
# Parameters
# ============================================================

CONFIG_FILE = "config.json"

# Номер камери, коли config.json недоступний, не має ключа
# `camera_index` або містить не ціле значення.
DEFAULT_CAMERA_INDEX = 0


# ============================================================
# Config
# ============================================================

def load_camera_index() -> int:
    """
    `camera_index` з config.json.

    Помилка читання не зупиняє програму - повертається
    `DEFAULT_CAMERA_INDEX`, тобто поточна поведінка до того, як ключ
    взагалі існував.
    """

    path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)

    try:

        with open(path, "r", encoding="utf-8") as f:

            value = json.load(f).get("camera_index", DEFAULT_CAMERA_INDEX)

        return int(value)

    except Exception as e:

        print(
            f"Error loading {CONFIG_FILE}: {e}. "
            f"Camera index {DEFAULT_CAMERA_INDEX}."
        )

        return DEFAULT_CAMERA_INDEX


class CameraReader:

    def __init__(self, camera_index=None):

        # None - взяти з config.json, інакше - явне значення викликача.
        if camera_index is None:

            camera_index = load_camera_index()

        self.camera_index = camera_index

        self.camera = cv2.VideoCapture(
            camera_index,
            cv2.CAP_DSHOW
        )

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.lock = threading.Lock()

        self.frame = None
        self.success = False

        self.running = False
        self.thread = None

    # ---------------------------------------------------------

    def start(self):

        self.running = True

        self.thread = threading.Thread(
            target=self._update,
            daemon=True
        )

        self.thread.start()

    # ---------------------------------------------------------

    def _update(self):

        while self.running:

            success, frame = self.camera.read()

            if success:

                with self.lock:

                    self.success = success
                    self.frame = frame

    # ---------------------------------------------------------

    def read(self):

        with self.lock:

            if self.frame is None:

                return False, None

            return True, self.frame.copy()

    # ---------------------------------------------------------

    def wait_first_frame(self, warn_after: float = 5.0, poll_interval: float = 0.01):
        """
        Очікування першого кадру з періодичним попередженням.

        Без попередження програма просто висить: вікно не з'являється, і
        невідомо, чи то не той індекс камери, чи пристрій не під'єднаний,
        чи його зайняла інша програма.
        """

        start = time.time()

        warned_at = start

        while True:

            success, frame = self.read()

            if success:

                return success, frame

            now = time.time()

            if now - warned_at >= warn_after:

                warned_at = now

                self._warn_no_frame(now - start)

            time.sleep(poll_interval)

    # ---------------------------------------------------------

    def _warn_no_frame(self, waited: float):

        if self.camera.isOpened():

            state = "кадрів не дає"

        else:

            state = "не відкрилась"

        print(
            f"Камера {self.camera_index} {state} (чекаємо {waited:.0f} с). "
            f"Перевір camera_index у {CONFIG_FILE} або під'єднай пристрій."
        )

    # ---------------------------------------------------------

    def stop(self):

        self.running = False

        if self.thread is not None:

            self.thread.join()

        self.camera.release()

        