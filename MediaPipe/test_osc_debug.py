"""
test_osc_debug.py

Перевірка відладочного виводу з osc_sender.py та grabcontroller.py:

    python -m pytest test_osc_debug.py
    python test_osc_debug.py

Мережа не використовується: `udp_client` підмінений заглушкою, а
`control.json` для перевірки `load_debug_flag()` створюється у
тимчасовому каталозі.
"""

from __future__ import annotations

import io
import contextlib
import json
import os
import shutil
import tempfile

import osc_sender as osc_sender_mod

from osc_sender import OSCSender, load_debug_flag
from grabcontroller import GrabController, UseController


# Коротке натискання в тестах: типові 0.1 с лише затягують прогін, а
# саму типову тривалість перевіряє test_use_press_duration_default.
PRESS_SECONDS = 0.02


# ============================================================
# Stubs
# ============================================================

class FakeClient:

    def __init__(self):

        self.messages = []

    def send_message(self, address, value):

        self.messages.append((address, value))


class FakeUDPModule:
    """
    Підміна модуля pythonosc.udp_client.
    """

    def __init__(self):

        self.clients = []

    def SimpleUDPClient(self, ip, port):

        client = FakeClient()

        self.clients.append(client)

        return client


class FakeLandmark:

    def __init__(self, visibility):

        self.visibility = visibility


def build(debug):
    """
    OSCSender без мережі, з увімкненим або вимкненим виводом.
    """

    udp = FakeUDPModule()

    osc_sender_mod.udp_client = udp

    sender = OSCSender(debug=debug)

    return sender, udp


def capture(function, *args, **kwargs):
    """
    Повертає (вивід у консоль, результат виклику).
    """

    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):

        result = function(*args, **kwargs)

    return buffer.getvalue(), result


def read_flag(payload):
    """
    Що поверне load_debug_flag() для control.json з вмістом payload
    (None — файлу немає зовсім).
    """

    directory = tempfile.mkdtemp(prefix="mp_debug_")

    if payload is not None:

        with open(os.path.join(directory, "control.json"), "w", encoding="utf-8") as f:

            f.write(payload)

    saved = osc_sender_mod.__file__

    osc_sender_mod.__file__ = os.path.join(directory, "osc_sender.py")

    try:

        text, value = capture(load_debug_flag)

    finally:

        osc_sender_mod.__file__ = saved

        shutil.rmtree(directory)

    return text, value


def pump(controller, visibilities):

    for visibility in visibilities:

        controller.update(FakeLandmark(visibility))


# ============================================================
# load_debug_flag
# ============================================================

def test_flag_true():

    _text, value = read_flag('{"debug": true}')

    assert value is True

    print("OK  debug: true вмикає вивід")


def test_flag_false():

    _text, value = read_flag('{"debug": false}')

    assert value is False

    print("OK  debug: false вимикає вивід")


def test_flag_defaults_to_off():

    for payload in (None, "{}", '{"debug": 0}', '{"debug": null}'):

        _text, value = read_flag(payload)

        assert value is False, payload

    print("OK  без ключа (або без файлу) вивід вимкнено")


def test_flag_survives_broken_json():

    text, value = read_flag('{"debug": tru')

    assert value is False

    assert "Debug output disabled" in text

    print("OK  пошкоджений control.json не ламає запуск")


def test_flag_matches_project_control_json():

    real = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "control.json"
    )

    with open(real, "r", encoding="utf-8") as f:

        expected = bool(json.load(f).get("debug", False))

    _text, value = capture(load_debug_flag)

    assert value == expected

    print("OK  load_debug_flag() збігається з поточним control.json")


# ============================================================
# Traces
# ============================================================

def test_debug_off_is_silent():

    sender, udp = build(debug=False)

    text, _result = capture(sender.send_look, 0.52, 0.1)

    assert text == ""

    text, _result = capture(sender.send_grab_right, True)

    assert text == ""

    # Команда при цьому все одно йде у VRChat.
    assert udp.clients[0].messages == [
        ("/input/LookHorizontal", 0.52),
        ("/input/LookVertical", 0.1),
        ("/input/GrabRight", True),
    ]

    print("OK  debug: false - тихо, але команди надсилаються")


def test_look_axes_are_reported():

    sender, _udp = build(debug=True)

    text, _result = capture(sender.send_look, 0.5234, -0.9)

    assert "/input/LookHorizontal = 0.523" in text
    assert "/input/LookVertical = -0.900" in text

    print("OK  обидві осі погляду виводяться зі значеннями")


def test_streaming_axis_prints_only_on_change():

    sender, _udp = build(debug=True)

    text, _result = capture(sender.send_horizontal, 0.5)

    assert text.count("LookHorizontal") == 1

    # Мікрозміни нижче за крок не повинні сипатись у консоль.
    for value in (0.5001, 0.5004, 0.5009):

        text, _result = capture(sender.send_horizontal, value)

        assert text == "", value

    text, _result = capture(sender.send_horizontal, 0.52)

    assert text.count("LookHorizontal") == 1

    print("OK  безперервна вісь друкується лише при зміні значення")


def test_clamped_value_is_reported():

    sender, _udp = build(debug=True)

    text, _result = capture(sender.send_look, 5.0, -5.0)

    assert "/input/LookHorizontal = 1.000" in text
    assert "/input/LookVertical = -1.000" in text

    print("OK  вивід показує обмежене значення, а не сире")


def test_bool_commands_are_events():

    sender, _udp = build(debug=True)

    text, _result = capture(sender.send_grab_right, True)

    assert "/input/GrabRight = True" in text

    # Повторна та сама подія друкується знову: це не потік.
    text, _result = capture(sender.send_grab_right, True)

    assert "/input/GrabRight = True" in text

    text, _result = capture(sender.send_drop_right, False)

    assert "/input/DropRight = False" in text

    print("OK  GrabRight та DropRight виводяться як події")


def test_center_reports_both_axes():

    sender, _udp = build(debug=True)

    text, _result = capture(sender.center)

    assert "/input/LookHorizontal = 0.000" in text
    assert "/input/LookVertical = 0.000" in text

    print("OK  center() показує обидві осі")


# ============================================================
# GrabController
# ============================================================

def test_action_prints_follow_debug():

    sender, _udp = build(debug=True)

    controller = GrabController(sender)

    text, _result = capture(pump, controller, [0.9])

    assert "Action: Grab" in text
    assert "OSC: /input/GrabRight = True" in text

    assert controller.grab_state is True

    print("OK  Action: Grab друкується, коли вивід увімкнено")


def test_action_prints_are_silent_without_debug():

    sender, udp = build(debug=False)

    controller = GrabController(sender)

    text, _result = capture(pump, controller, [0.9])

    assert text == ""

    assert udp.clients[0].messages == [("/input/GrabRight", True)]

    print("OK  без виводу подія хоп не друкується взагалі")


def test_action_drop_prints_when_enabled():

    sender, _udp = build(debug=True)

    controller = GrabController(sender)

    capture(pump, controller, [0.9])

    text, _result = capture(pump, controller, [0.1, 0.1, 0.1])

    assert "Action: Drop" in text
    assert "OSC: /input/GrabRight = False" in text

    assert controller.grab_state is False

    print("OK  розтиснення теж друкується")


# ============================================================
# UseController
# ============================================================

def wait_press(controller, timeout=5.0):

    if controller.press_thread is not None:

        controller.press_thread.join(timeout)

        assert not controller.press_thread.is_alive()


def test_use_pulses_once_per_gesture():

    sender, udp = build(debug=True)

    controller = UseController(sender, PRESS_SECONDS)

    text, _result = capture(pump, controller, [0.9])

    wait_press(controller)

    assert udp.clients[0].messages == [
        ("/input/UseRight", True),
        ("/input/UseRight", False),
    ]

    assert "OSC: /input/UseRight = True" in text
    assert "Action: Use" in text

    print("OK  жест лівою кистю дає один імпульс UseRight")


def test_use_is_silent_without_debug():

    sender, udp = build(debug=False)

    controller = UseController(sender, PRESS_SECONDS)

    text, _result = capture(pump, controller, [0.9])

    wait_press(controller)

    assert text == ""

    assert udp.clients[0].messages == [
        ("/input/UseRight", True),
        ("/input/UseRight", False),
    ]

    print("OK  без виводу імпульс надсилається, але мовчки")


def test_use_does_not_repeat_while_hand_is_up():

    sender, udp = build(debug=False)

    controller = UseController(sender, PRESS_SECONDS)

    capture(pump, controller, [0.9] * 20)

    wait_press(controller)

    assert udp.clients[0].messages == [
        ("/input/UseRight", True),
        ("/input/UseRight", False),
    ]

    print("OK  рука, піднята і тримана, не спамить UseRight")


def test_use_rearms_after_hand_hides():

    sender, udp = build(debug=False)

    controller = UseController(sender, PRESS_SECONDS)

    capture(pump, controller, [0.9])

    wait_press(controller)

    # Рука зникла три кадри поспіль - жест знову готовий.
    capture(pump, controller, [0.1, 0.1, 0.1])

    capture(pump, controller, [0.9])

    wait_press(controller)

    assert udp.clients[0].messages == [
        ("/input/UseRight", True),
        ("/input/UseRight", False),
        ("/input/UseRight", True),
        ("/input/UseRight", False),
    ]

    print("OK  після опускання руки жест спрацьовує знову")


def test_use_press_duration_default():

    sender, _udp = build(debug=False)

    assert UseController(sender).USE_PRESS_SECONDS == 0.1

    print("OK  типова тривалість натискання - 0.1 с")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    print("------------------------------------")
    print("osc_sender.py / grabcontroller.py checks")
    print("------------------------------------")

    test_flag_true()
    test_flag_false()
    test_flag_defaults_to_off()
    test_flag_survives_broken_json()
    test_flag_matches_project_control_json()
    test_debug_off_is_silent()
    test_look_axes_are_reported()
    test_streaming_axis_prints_only_on_change()
    test_clamped_value_is_reported()
    test_bool_commands_are_events()
    test_center_reports_both_axes()
    test_action_prints_follow_debug()
    test_action_prints_are_silent_without_debug()
    test_action_drop_prints_when_enabled()
    test_use_pulses_once_per_gesture()
    test_use_is_silent_without_debug()
    test_use_does_not_repeat_while_hand_is_up()
    test_use_rearms_after_hand_hides()
    test_use_press_duration_default()

    print("------------------------------------")
    print("All checks passed.")
