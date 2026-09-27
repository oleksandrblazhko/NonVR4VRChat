"""
test_interface.py

Перевірка клавіатурного інтерфейсу з interface.py без камери та VRChat:

    python test_interface.py

Залежності (калібрування, контролер погляду, OSC), а також годинник і
звук підмінені заглушками, щоб перевірка була детермінованою і миттєвою.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import interface as interface_mod

from interface import Interface, BAR_HEIGHT


# ============================================================
# Stubs
# ============================================================

class FakeClock:
    """
    Годинник, час у якому рухає сам тест.
    """

    def __init__(self, now: float = 0.0):

        self.now = now

        self.sleeps = 0

    def time(self) -> float:

        return self.now

    def sleep(self, seconds: float):

        # Потік зворотного відліку не повинен рухати час,
        # інакше перевірка стає перегонів з ним.
        self.sleeps += 1


class FakeSound:
    """
    Заглушка winsound: замість гудків рахує виклики.
    """

    def __init__(self):

        self.beeps = []

    def Beep(self, frequency, duration):

        self.beeps.append((frequency, duration))


class FakeCalibration:

    def __init__(self):

        self.ready = False

        self.neutral = None

        self.reset_calls = 0

        self.print_calls = 0

    def set_neutral(self, yaw, pitch):

        self.neutral = (yaw, pitch)

        self.ready = True

    def reset(self):

        self.neutral = None

        self.ready = False

        self.reset_calls += 1

    def is_ready(self):

        return self.ready

    def print(self):

        self.print_calls += 1


class FakeLookController:

    def __init__(self):

        self.reset_calls = 0

    def reset(self):

        self.reset_calls += 1


class FakeOsc:

    def __init__(self):

        self.center_calls = 0

    def center(self):

        self.center_calls += 1


def build(calibration_time=4.0):
    """
    Інтерфейс із підміненими годинником і звуком.
    """

    clock = FakeClock(100.0)

    sound = FakeSound()

    interface_mod.time = clock

    interface_mod.winsound = sound

    calibration = FakeCalibration()

    look = FakeLookController()

    osc = FakeOsc()

    iface = Interface(
        calibration,
        look,
        osc,
        calibration_time=calibration_time
    )

    return iface, clock, sound, calibration, look, osc


def wait_countdown(iface, timeout=5.0):

    if iface.countdown_thread is not None:

        iface.countdown_thread.join(timeout)

        assert not iface.countdown_thread.is_alive()


def assert_neutral(calibration, yaw, pitch):

    assert calibration.neutral is not None

    # Усереднення плаваючою точкою дає лише наближені значення.
    assert abs(calibration.neutral[0] - yaw) < 1e-9
    assert abs(calibration.neutral[1] - pitch) < 1e-9


# ============================================================
# Keys
# ============================================================

def test_escape_requests_quit():

    iface, _clock, _sound, _cal, _look, _osc = build()

    assert iface.handle_key(27) is True

    print("OK  ESC повертає запит на вихід")


def test_reset_keys():

    for key in (ord("r"), ord("R")):

        iface, _clock, _sound, cal, look, osc = build()

        assert iface.handle_key(key) is False

        assert cal.reset_calls == 1
        assert look.reset_calls == 1
        assert osc.center_calls == 1

    print("OK  r та R скидають калібрування, погляд і OSC")


def test_unknown_key_ignored():

    iface, _clock, _sound, cal, look, osc = build()

    assert iface.handle_key(-1) is False

    assert iface.handle_key(ord("z")) is False

    assert cal.reset_calls == 0
    assert look.reset_calls == 0
    assert osc.center_calls == 0
    assert iface.calibrating is False

    print("OK  невідома клавіша не має побічних ефектів")


# ============================================================
# Calibration session
# ============================================================

def test_calibration_averages_samples():

    iface, clock, sound, cal, look, osc = build()

    assert iface.handle_key(ord("1")) is False

    assert iface.calibrating is True

    clock.now = 100.5

    iface.update(0.1, 0.2)

    assert cal.neutral is None
    assert iface.calibrating is True

    clock.now = 104.5

    iface.update(0.3, 0.4)

    assert iface.calibrating is False

    assert_neutral(cal, 0.2, 0.3)

    assert cal.ready is True

    # Завершення калібрування скидає погляд і надсилає центр OSC.
    assert look.reset_calls == 1
    assert osc.center_calls == 1
    assert cal.print_calls == 1

    # Зворотний відлік відпрацював на підміненому звуці.
    wait_countdown(iface)

    assert sound.beeps == [(1000, 200), (1000, 200), (1000, 700)]

    print("OK  калібрування усереднює зразки та завершується за час")


def test_second_press_while_calibrating_is_ignored():

    iface, clock, sound, cal, _look, _osc = build()

    iface.handle_key(ord("1"))

    clock.now = 100.5

    iface.update(0.1, 0.2)

    iface.handle_key(ord("1"))

    assert iface.sum_yaw_metric == 0.1
    assert iface.sum_pitch_metric == 0.2
    assert iface.sample_count == 1

    clock.now = 104.5

    iface.update(0.3, 0.4)

    assert_neutral(cal, 0.2, 0.3)

    wait_countdown(iface)

    # Другого запуску відліку не було: гудків саме три.
    assert len(sound.beeps) == 3

    print("OK  повторне 1 під час калібрування не скидає зразки")


def test_update_without_calibration_does_nothing():

    iface, _clock, _sound, cal, look, osc = build()

    iface.update(0.9, 0.9)

    assert iface.sample_count == 0
    assert cal.neutral is None
    assert look.reset_calls == 0
    assert osc.center_calls == 0

    print("OK  update() поза сесією калібрування нічого не робить")


def test_reset_during_calibration_is_not_cancelled():

    iface, clock, _sound, cal, _look, _osc = build()

    iface.handle_key(ord("1"))

    iface.handle_key(ord("r"))

    assert cal.ready is False

    # Поведінка перенесена з main.py без змін: сесія доживає до кінця
    # і знову записує нейтраль, хоча калібрування вже скинуте.
    clock.now = 104.5

    iface.update(0.2, 0.2)

    assert_neutral(cal, 0.2, 0.2)

    wait_countdown(iface)

    print("OK  R під час калібрування не скасовує сесію (як і раніше)")


# ============================================================
# Display
# ============================================================

def test_hints_line_at_bottom():

    iface, _clock, _sound, _cal, _look, _osc = build()

    frame = np.full((480, 640, 3), 255, dtype=np.uint8)

    iface.draw_hints(frame)

    # Верх кадру не чіпаємо.
    assert frame[:100].min() == 255

    bottom = frame[480 - BAR_HEIGHT:]

    black = np.all(bottom == 0, axis=-1)

    green = np.all(bottom == np.array([0, 255, 0]), axis=-1)

    # Смуга мальована, і на ній є текст.
    assert black.sum() > 1000
    assert green.sum() > 200

    print("OK  рядок-підказка у нижній частині кадру")


def test_hints_line_on_small_frame():

    iface, _clock, _sound, _cal, _look, _osc = build()

    frame = np.zeros((20, 320, 3), dtype=np.uint8)

    iface.draw_hints(frame)

    assert frame.shape == (20, 320, 3)

    # Навіть на кадрі меншому за смугу текст має залишитись у межах кадру.
    green = np.all(frame == np.array([0, 255, 0]), axis=-1)

    assert green.sum() > 0

    print("OK  підказка не ламається на кадрі меншому за смугу")


def test_status_shows_calibration_state():

    iface, clock, _sound, cal, _look, _osc = build()

    # 1. Калібрування ще не було - жовте попередження.
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    iface.draw_status(frame)

    yellow = np.all(frame == np.array([0, 255, 255]), axis=-1)

    red = np.all(frame == np.array([0, 0, 255]), axis=-1)

    assert yellow.sum() > 500
    assert red.sum() == 0

    # 2. Активна сесія - червоний індикатор замість попередження.
    iface.handle_key(ord("1"))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    iface.draw_status(frame)

    red = np.all(frame == np.array([0, 0, 255]), axis=-1)

    yellow = np.all(frame == np.array([0, 255, 255]), axis=-1)

    assert red.sum() > 500
    assert yellow.sum() == 0

    clock.now = 104.5

    iface.update(0.0, 0.0)

    assert iface.calibrating is False

    wait_countdown(iface)

    # 3. Відкалібровано і сесії немає - на екрані чисто.
    assert cal.ready is True

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    iface.draw_status(frame)

    assert frame.max() == 0

    print("OK  статус: попередження -> CALIBRATION... -> чисто")


def test_banner_lists_keys(capsys=None):

    import io
    import contextlib

    iface, _clock, _sound, _cal, _look, _osc = build()

    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):

        iface.print_banner()

    printed = buffer.getvalue()

    for key, label in interface_mod.KEY_HINTS:

        assert f"{key} - {label.lower()}" in printed

    assert "VRChat Body Tracker" in printed

    print("OK  банер у консолі перелічує ті самі клавіші")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    print("------------------------------------")
    print("interface.py checks")
    print("------------------------------------")

    test_escape_requests_quit()
    test_reset_keys()
    test_unknown_key_ignored()
    test_calibration_averages_samples()
    test_second_press_while_calibrating_is_ignored()
    test_update_without_calibration_does_nothing()
    test_reset_during_calibration_is_not_cancelled()
    test_hints_line_at_bottom()
    test_hints_line_on_small_frame()
    test_status_shows_calibration_state()
    test_banner_lists_keys()

    print("------------------------------------")
    print("All checks passed.")
