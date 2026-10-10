"""
interface.py

Клавіатурний інтерфейс додатку.

Тут зосереджено все, що пов'язано з гарячими клавішами вікна OpenCV:

    1   - калібрування
    R   - скидання
    ESC - вихід

    Shift + / -  - чутливість по горизонталі (LookH)
    Ctrl  + / -  - чутливість по вертикалі   (LookV)

Модуль читає натиснуту клавішу, виконує її дію (калібрування, скидання
або запит на вихід) та малює у вікні підсвітку стану калібрування і
нижній рядок з підказками.

Текст на кадрі набирається латиницею, бо Hershey-шрифти `cv2.putText`
не підтримують кирилицю.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
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

# Чутливість у відсотках (того ж масштабу, що й *_sensitivity_pct у
# config.json): крок на одне натискання, межі та назви атрибутів
# LookController, які регулюються.
SENSITIVITY_STEP = 2.0

SENSITIVITY_MIN = 1.0

SENSITIVITY_MAX = 100.0

SENSITIVITY_ATTRS = {
    "h": "horizontal_sensitivity_pct",
    "v": "vertical_sensitivity_pct",
}

# Імена клавіш у бібліотеці `keyboard` (залежать від розкладки/нумпаду).
KEYS_PLUS = ("+", "=", "plus", "add")

KEYS_MINUS = ("-", "_", "minus", "subtract")

CONFIG_FILE = "config.json"

# Віртуальні коди клавіш Windows (GetAsyncKeyState).
VK_SHIFT = 0x10

VK_CONTROL = 0x11

VK_PLUS = (0xBB, 0x6B)    # OEM_PLUS (=/+), NumPad +

VK_MINUS = (0xBD, 0x6D)   # OEM_MINUS (-/_), NumPad -

# Підписи регулювання чутливості для консольного банера.
SENSITIVITY_HINTS = (
    ("Shift + / -", "sensitivity LookH"),
    ("Ctrl  + / -", "sensitivity LookV"),
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

        # Опитування клавіш Windows, див. start_hotkeys().
        self._user32 = None

        self._held = set()

        # Чи змінювалась чутливість з моменту завантаження/збереження.
        self._settings_dirty = False

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
    # Sensitivity
    # --------------------------------------------------------

    def sensitivity(self, axis: str) -> float | None:
        """
        Поточна чутливість осі (`"h"` або `"v"`) у відсотках.

        None, якщо контролер погляду не має такого параметра.
        """

        return getattr(
            self.look_controller,
            SENSITIVITY_ATTRS[axis],
            None
        )

    # --------------------------------------------------------

    def adjust_sensitivity(self, axis: str, direction: int):
        """
        Змінити чутливість осі на один крок (`direction` = +1 або -1).

        Значення обмежується діапазоном [SENSITIVITY_MIN; SENSITIVITY_MAX].
        Повертає нове значення або None, якщо параметра немає.
        """

        current = self.sensitivity(axis)

        if current is None:

            return None

        value = current + direction * SENSITIVITY_STEP

        value = max(SENSITIVITY_MIN, min(SENSITIVITY_MAX, value))

        setattr(
            self.look_controller,
            SENSITIVITY_ATTRS[axis],
            value
        )

        if value != current:

            self._settings_dirty = True

        name = "LookH" if axis == "h" else "LookV"

        print(f"Sensitivity {name}: {value:.0f}%")

        return value

    # --------------------------------------------------------

    def handle_hotkey(
            self,
            name: str,
            shift: bool,
            ctrl: bool
    ) -> bool:
        """
        Обробити натискання `+`/`-` разом з модифікатором.

            Shift + / -  -> горизонталь
            Ctrl  + / -  -> вертикаль

        Без модифікатора або з обома одразу клавіша ігнорується.
        Повертає True, якщо чутливість було оброблено.
        """

        name = (name or "").lower()

        if name in KEYS_PLUS:

            direction = 1

        elif name in KEYS_MINUS:

            direction = -1

        else:

            return False

        if shift and not ctrl:

            axis = "h"

        elif ctrl and not shift:

            axis = "v"

        else:

            return False

        return self.adjust_sensitivity(axis, direction) is not None

    # --------------------------------------------------------

    def start_hotkeys(self) -> bool:
        """
        Увімкнути глобальні хоткеї чутливості (лише Windows).

        `cv2.waitKey` не бачить Shift/Ctrl, тому стан клавіш читається
        напряму через WinAPI. Працює і тоді, коли у фокусі VRChat, без
        додаткових бібліотек та прав адміністратора. Самі натискання
        обробляє poll_hotkeys(), яку треба викликати щокадру.
        """

        if sys.platform != "win32":

            print("Хоткеї чутливості вимкнено: потрібна Windows.")

            return False

        try:

            self._user32 = ctypes.windll.user32

        except Exception as e:

            print(f"Хоткеї чутливості вимкнено: {e}")

            self._user32 = None

            return False

        return True

    # --------------------------------------------------------

    def stop_hotkeys(self):
        """
        Вимкнути опитування хоткеїв.
        """

        self._user32 = None

        self._held.clear()

    # --------------------------------------------------------

    def _down(self, vk: int) -> bool:

        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    # --------------------------------------------------------

    def poll_hotkeys(self):
        """
        Перевірити Shift/Ctrl + `+`/`-`. Викликати щокадру.

        Одне натискання клавіші дає один крок.
        """

        if self._user32 is None:

            return

        shift = self._down(VK_SHIFT)

        ctrl = self._down(VK_CONTROL)

        for direction, codes in ((1, VK_PLUS), (-1, VK_MINUS)):

            pressed = any(self._down(vk) for vk in codes)

            if not pressed:

                self._held.discard(direction)

                continue

            if direction in self._held:

                continue

            self._held.add(direction)

            if shift and not ctrl:

                self.adjust_sensitivity("h", direction)

            elif ctrl and not shift:

                self.adjust_sensitivity("v", direction)

    # --------------------------------------------------------

    def save_settings(self) -> bool:
        """
        Записати чутливість у `config.json` (секція `var_settings`),
        якщо вона змінювалась. Решта ключів файлу зберігається.
        """

        if not self._settings_dirty:

            return False

        path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)

        try:

            with open(path, "r", encoding="utf-8") as f:

                config = json.load(f)

            settings = config.setdefault("var_settings", {})

            for axis, attr in SENSITIVITY_ATTRS.items():

                value = self.sensitivity(axis)

                if value is not None:

                    settings[attr] = value

            with open(path, "w", encoding="utf-8") as f:

                json.dump(config, f, indent=2, ensure_ascii=False)

                f.write("\n")

        except Exception as e:

            print(f"Не вдалось зберегти {CONFIG_FILE}: {e}")

            return False

        self._settings_dirty = False

        print(f"Чутливість збережено у {CONFIG_FILE}.")

        return True

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

    def render_display(
        self,
        frame,
        look_horizontal: float | None = None,
        look_vertical: float | None = None,
        grab_state: bool = False,
        use_triggered: bool = False,
    ):
        """
        Створює кадр для відображення: додає знизу панель
        з телеметрією (LookH, LookV, Grab, Use) та підказками гарячих клавіш.
        """
        h, w = frame.shape[:2]
        panel_h = 76

        # Додаємо чорну панель знизу, не чіпаючи корисний відеокадр
        display_frame = cv2.copyMakeBorder(
            frame,
            0,
            panel_h,
            0,
            0,
            cv2.BORDER_CONSTANT,
            value=(0, 0, 0)
        )

        # Розділювальна лінія між відео та панеллю
        cv2.line(display_frame, (0, h), (w, h), (50, 50, 50), 1)

        # ----------------------------------------------------
        # Рядок 1: Телеметрія
        # ----------------------------------------------------
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.45
        thickness = 1
        y1 = h + 20

        # Розраховуємо 4 рівномірні колонки
        col_w = w // 4

        # 1. LookH
        lh_text = "--" if look_horizontal is None else f"{look_horizontal:+.3f}"
        lh_color = (150, 150, 150) if look_horizontal is None else (255, 255, 0)
        cv2.putText(display_frame, "LookH: ", (15, y1), font, font_scale, (180, 180, 180), thickness)
        (tw, _), _ = cv2.getTextSize("LookH: ", font, font_scale, thickness)
        cv2.putText(display_frame, lh_text, (15 + tw, y1), font, font_scale, lh_color, thickness)

        # 2. LookV
        lv_text = "--" if look_vertical is None else f"{look_vertical:+.3f}"
        lv_color = (150, 150, 150) if look_vertical is None else (255, 255, 0)
        x2 = col_w + 10
        cv2.putText(display_frame, "LookV: ", (x2, y1), font, font_scale, (180, 180, 180), thickness)
        (tw, _), _ = cv2.getTextSize("LookV: ", font, font_scale, thickness)
        cv2.putText(display_frame, lv_text, (x2 + tw, y1), font, font_scale, lv_color, thickness)

        # 3. Grab
        x3 = col_w * 2 + 10
        grab_text = "Active" if grab_state else "Dropped"
        grab_color = (0, 255, 0) if grab_state else (140, 140, 140)
        cv2.putText(display_frame, "Grab: ", (x3, y1), font, font_scale, (180, 180, 180), thickness)
        (tw, _), _ = cv2.getTextSize("Grab: ", font, font_scale, thickness)
        cv2.putText(display_frame, grab_text, (x3 + tw, y1), font, font_scale, grab_color, thickness)

        # 4. Use
        x4 = col_w * 3 + 10
        use_text = "Triggered" if use_triggered else "Idle"
        use_color = (0, 215, 255) if use_triggered else (140, 140, 140)
        cv2.putText(display_frame, "Use: ", (x4, y1), font, font_scale, (180, 180, 180), thickness)
        (tw, _), _ = cv2.getTextSize("Use: ", font, font_scale, thickness)
        cv2.putText(display_frame, use_text, (x4 + tw, y1), font, font_scale, use_color, thickness)

        # Тонкий внутрішній розділювач між рядками 1 та 2
        cv2.line(display_frame, (10, h + 29), (w - 10, h + 29), (35, 35, 35), 1)

        # ----------------------------------------------------
        # Рядок 2: Чутливість (під колонками LookH / LookV)
        # ----------------------------------------------------
        y2 = h + 47
        label_color = (180, 180, 180)
        sens_color = (255, 200, 0)

        for x, label, axis in (
                (15, "SensH: ", "h"),
                (col_w + 10, "SensV: ", "v"),
        ):
            value = self.sensitivity(axis)
            text = "--" if value is None else f"{value:.0f}%"
            color = (150, 150, 150) if value is None else sens_color
            cv2.putText(display_frame, label, (x, y2), font, font_scale, label_color, thickness)
            (tw, _), _ = cv2.getTextSize(label, font, font_scale, thickness)
            cv2.putText(display_frame, text, (x + tw, y2), font, font_scale, color, thickness)

        cv2.putText(
            display_frame,
            "Shift +/- : H     Ctrl +/- : V",
            (col_w * 2 + 10, y2),
            font,
            font_scale,
            (140, 140, 140),
            thickness
        )

        cv2.line(display_frame, (10, h + 56), (w - 10, h + 56), (35, 35, 35), 1)

        # ----------------------------------------------------
        # Рядок 3: Гарячі клавіші
        # ----------------------------------------------------
        hints_text = "   ".join(f"[{key}] {label}" for key, label in KEY_HINTS)
        (hw, _), _ = cv2.getTextSize(hints_text, font, 0.45, 1)
        y3 = h + 69
        cv2.putText(
            display_frame,
            hints_text,
            (max((w - hw) // 2, 0), y3),
            font,
            0.45,
            HINT_COLOR,
            1
        )

        return display_frame

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

        for key, label in SENSITIVITY_HINTS:

            print(f"{key} - {label}")

        print("------------------------------------")