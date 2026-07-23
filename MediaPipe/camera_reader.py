"""
camera_reader.py

Окремий потік для захоплення кадрів з камери.
У пам'яті завжди зберігається лише останній кадр.
"""

import threading
import cv2


class CameraReader:

    def __init__(self, camera_index=0):

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

    def stop(self):

        self.running = False

        if self.thread is not None:

            self.thread.join()

        self.camera.release()

        