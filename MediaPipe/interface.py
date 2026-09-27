"""
interface.py

Клавіатурний інтерфейс додатку.

Тут зосереджено все, що пов'язано з гарячими клавішами вікна OpenCV:

    1   - калібрування
    R   - скидання
    ESC - вихід

Модуль читає натиснуту клавішу, виконує її дію (калібрування, скидання
або запит на вихід) та малює у вікні підсвітку стану калібрування і
нижній рядок з підказками.

Текст на кадрі набирається латиницею, бо Hershey-шрифти `cv2.putText`
не підтримують кирилицю.
"""

from __future__ import annotations

import time
import threading

import cv2
import winsound


# ============================================================
# Parameters
# ============================================================

CALIBRATION_TIME = 4.0

KEY_ESCAPE = 27

KEY_CALIBRATE = ord("1")

KEY_RESET = (ord("r"), ord("R"))

# Гарячі клавіші та їхні підписи: один список живить
# і консольний банер, і рядок-підказку внизу кадру.
KEY_HINTS = (
    ("1", "Calibration"),
    ("R", "Reset"),
    ("ESC", "Quit"),
)

HINT_FONT = cv2.FONT_HERSHEY_SIMPLEX

HINT_SCALE = 0.55

HINT_THICKNESS = 1

HINT_COLOR = (0, 255, 0)

BAR_COLOR = (0, 0, 0)

BAR_HEIGHT = 28

STATUS_FONT = cv2.FONT_HERSHEY_SIMPLEX

STATUS_COLOR = (0, 0, 255)

WARNING_COLOR = (0, 255, 255)


# ============================================================
# Interface
# ============================================================

class Interface:
    """
    Клавіатура, сесія калібрування та підказки на екрані.
    """

    # --------------------------------------------------------

    def __init__(
            self,
            calibration,
            look_controller,
            osc,
            calibration_time: float = CALIBRATION_TIME
    ):

        self.calibration = calibration

        self.look_controller = look_controller

        self.osc = osc

        self.calibration_time = calibration_time

        self.calibrating = False

        self.countdown_thread = None

        self.sum_yaw_metric = 0.0

        self.sum_pitch_metric = 0.0

        self.sample_count = 0

        self.calibration_start = 0.0

    # --------------------------------------------------------
    # Keyboard
    # --------------------------------------------------------

    def read_key(self) -> int:
        """
        Отримати клавішу, натиснуту у вікні.
        """

        return cv2.waitKey(1)

    # --------------------------------------------------------

    def handle_key(self, key: int) -> bool:
        """
        Обробити гарячу клавішу.

        Повертає True, якщо програму треба завершити.
        """

        if key == KEY_ESCAPE:

            return True

        elif key == KEY_CALIBRATE:

            self.start_calibration()

        elif key in KEY_RESET:

            self.reset()

        return False

    # --------------------------------------------------------
    # Calibration
    # --------------------------------------------------------

    def start_calibration(self):
        """
        Розпочати сесію калібрування (клавіша `1`).
        """

        if self.calibrating:

            return

        self.calibrating = True

        self.calibration_start = time.time()

        self.sum_yaw_metric = 0.0

        self.sum_pitch_metric = 0.0

        self.sample_count = 0

        countdown_thread = threading.Thread(
            target=self._countdown
        )

        countdown_thread.daemon = True

        self.countdown_thread = countdown_thread

        countdown_thread.start()

    # --------------------------------------------------------

    def update(self, yaw_metric: float, pitch_metric: float):
        """
        Накопичити зразок метрик для калібрування.

        Викликати на кожному кадрі з виявленою позою.
        """

        if not self.calibrating:

            return

        self.sum_yaw_metric += yaw_metric

        self.sum_pitch_metric += pitch_metric

        self.sample_count += 1

        elapsed = time.time() - self.calibration_start

        if elapsed < self.calibration_time:

            return

        self.calibration.set_neutral(
            self.sum_yaw_metric / self.sample_count,
            self.sum_pitch_metric / self.sample_count
        )

        self.calibrating = False

        self.look_controller.reset()

        self.osc.center()

        print()
        print("Calibration completed.")

        self.calibration.print()

    # --------------------------------------------------------

    def reset(self):
        """
        Скинути калібрування (клавіша `R`).
        """

        print()
        print("Reset.")

        self.calibration.reset()

        self.look_controller.reset()

        self.osc.center()

    # --------------------------------------------------------

    def _countdown(self):
        """
        Програвання зворотного відліку калібрування.
        """

        print("Режим калібрування. Тримайте тіло у стані спокою впродовж декількох секунд")

        for i in range(3, 0, -1):

            print(f"{i}.......")

            if i == 1:
                winsound.Beep(1000, 700) # Final beep for 1
            else:
                winsound.Beep(1000, 200) # Short beeps for 3 and 2

            time.sleep(1)

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    def draw_status(self, frame):
        """
        Стан калібрування у лівому верхньому куті.

        Викликається поза гілкою з виявленою позою, щоб попередження не
        зникало, коли камера втратить користувача. Рядок `Pose not
        detected` малює `main.py`, і він стоїть вище - за координатами
        вони не перекриваються.
        """

        if self.calibrating:

            cv2.putText(
                frame,
                "CALIBRATION...",
                (10, 80),
                STATUS_FONT,
                0.8,
                STATUS_COLOR,
                2
            )

        elif not self.calibration.is_ready():

            cv2.putText(
                frame,
                "NO CALIBRATION - PRESS 1",
                (10, 80),
                STATUS_FONT,
                0.8,
                WARNING_COLOR,
                2
            )

    # --------------------------------------------------------

    def draw_hints(self, frame):
        """
        Нижній рядок з підказками про гарячі клавіші.
        """

        h, w = frame.shape[:2]

        text = "   ".join(
            f"[{key}] {label}"
            for key, label in KEY_HINTS
        )

        (text_w, text_h), _ = cv2.getTextSize(
            text,
            HINT_FONT,
            HINT_SCALE,
            HINT_THICKNESS
        )

        top = max(h - BAR_HEIGHT, 0)

        cv2.rectangle(
            frame,
            (0, top),
            (w, h),
            BAR_COLOR,
            cv2.FILLED
        )

        cv2.putText(
            frame,
            text,
            (max((w - text_w) // 2, 0), h - max((BAR_HEIGHT - text_h) // 2, 0)),
            HINT_FONT,
            HINT_SCALE,
            HINT_COLOR,
            HINT_THICKNESS
        )

    # --------------------------------------------------------

    def print_banner(self):
        """
        Опис керування у консолі на старті.
        """

        print("------------------------------------")
        print("VRChat Body Tracker")
        print()

        for key, label in KEY_HINTS:

            print(f"{key} - {label.lower()}")

        print("------------------------------------")
