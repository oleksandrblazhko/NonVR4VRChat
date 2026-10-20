"""
test_profiles.py

Перевірка профілів користувачів (profiles.py) та їхньої інтеграції з
LookController і Interface без камери та VRChat:

    python test_profiles.py

Справжній config.json не чіпається: кожна перевірка працює з файлом у
тимчасовому каталозі. winsound на не-Windows підміняється заглушкою.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if "winsound" not in sys.modules:

    try:

        import winsound  # noqa: F401

    except ImportError:

        stub = types.ModuleType("winsound")
        stub.Beep = lambda frequency, duration: None
        sys.modules["winsound"] = stub

from profiles import ProfileManager, PROFILE_DEFAULTS
from look_controller import LookController
from interface import Interface


# ============================================================
# Helpers
# ============================================================

def make_config(directory: str, payload) -> str:

    path = os.path.join(directory, "config.json")

    with open(path, "w", encoding="utf-8") as f:

        if isinstance(payload, str):

            f.write(payload)

        else:

            json.dump(payload, f)

    return path


def two_profiles() -> dict:

    return {
        "debug": True,
        "camera_index": 2,
        "active_profile": "B",
        "profiles": [
            {"name": "A", "horizontal_sensitivity_pct": 10.0, "smooth": 0.1},
            {"name": "B", "horizontal_sensitivity_pct": 40.0, "smooth": 0.3},
        ],
    }


class FakeCalibration:

    def reset(self):
        pass

    def is_ready(self):
        return True


class FakeOsc:

    def __init__(self):
        self.center_calls = 0

    def center(self):
        self.center_calls += 1


def build(path: str):

    manager = ProfileManager(path)

    look = LookController(manager)

    osc = FakeOsc()

    iface = Interface(FakeCalibration(), look, osc, profiles=manager)

    return manager, look, osc, iface


# ============================================================
# Loading
# ============================================================

def test_loads_profiles_and_active():

    with tempfile.TemporaryDirectory() as d:

        manager = ProfileManager(make_config(d, two_profiles()))

        assert manager.names == ["A", "B"]
        assert manager.active_name == "B"
        assert manager.active_settings["horizontal_sensitivity_pct"] == 40.0
        # Відсутні параметри добираються зі значень за замовчуванням.
        assert manager.active_settings["max_vertical_metric"] == \
            PROFILE_DEFAULTS["max_vertical_metric"]

    print("OK  профілі та active_profile читаються, пропуски добираються")


def test_legacy_var_settings_becomes_default_profile():

    with tempfile.TemporaryDirectory() as d:

        path = make_config(d, {"var_settings": {"smooth": 0.7}})

        manager = ProfileManager(path)

        assert manager.names == ["Default"]
        assert manager.active_settings["smooth"] == 0.7

    print("OK  старий формат var_settings читається як профіль Default")


def test_missing_or_broken_file_falls_back():

    with tempfile.TemporaryDirectory() as d:

        missing = ProfileManager(os.path.join(d, "none.json"))

        assert missing.names == ["Default"]
        assert missing.active_settings == PROFILE_DEFAULTS

        broken = ProfileManager(make_config(d, "{ not json"))

        assert broken.names == ["Default"]

        not_object = ProfileManager(make_config(d, "[1, 2]"))

        assert not_object.names == ["Default"]

    print("OK  немає файлу / битий JSON / корінь-масив - профіль за замовчуванням")


def test_duplicate_and_unknown_active():

    with tempfile.TemporaryDirectory() as d:

        payload = {
            "active_profile": "Nope",
            "profiles": [{"name": "A"}, {"name": "A"}, {"name": "B"}],
        }

        manager = ProfileManager(make_config(d, payload))

        assert manager.names == ["A", "B"]
        assert manager.active_name == "A"

    print("OK  дублі назв відкидаються, невідомий active_profile -> перший")


# ============================================================
# Switching
# ============================================================

def test_switch_wraps_around():

    with tempfile.TemporaryDirectory() as d:

        manager = ProfileManager(make_config(d, two_profiles()))

        assert manager.switch(1) == "A"
        assert manager.switch(1) == "B"
        assert manager.switch(-1) == "A"
        assert manager.switch(-1) == "B"
        assert manager.select("A") is True
        assert manager.select("Z") is False
        assert manager.active_name == "A"

    print("OK  перемикання по колу в обидва боки, select за назвою")


def test_save_keeps_other_keys_and_drops_var_settings():

    with tempfile.TemporaryDirectory() as d:

        payload = two_profiles()
        payload["var_settings"] = {"smooth": 0.9}

        path = make_config(d, payload)

        manager = ProfileManager(path)
        manager.switch(1)
        manager.update_active({"smooth": 0.5, "unknown_key": 1})

        assert manager.save() is True

        with open(path, encoding="utf-8") as f:

            saved = json.load(f)

        assert saved["debug"] is True
        assert saved["camera_index"] == 2
        assert "var_settings" not in saved
        assert saved["active_profile"] == "A"
        assert saved["profiles"][0]["smooth"] == 0.5
        assert "unknown_key" not in saved["profiles"][0]

    print("OK  збереження: чужі ключі лишаються, var_settings зникає")


def test_save_does_not_overwrite_unreadable_file():

    with tempfile.TemporaryDirectory() as d:

        path = make_config(d, two_profiles())

        manager = ProfileManager(path)

        with open(path, "w", encoding="utf-8") as f:

            f.write("{ broken")

        assert manager.save() is False

        with open(path, encoding="utf-8") as f:

            assert f.read() == "{ broken"

    print("OK  нечитабельний config.json не перетирається")


# ============================================================
# LookController / Interface
# ============================================================

def test_look_controller_uses_active_profile():

    with tempfile.TemporaryDirectory() as d:

        _manager, look, _osc, _iface = build(make_config(d, two_profiles()))

        assert look.horizontal_sensitivity_pct == 40.0
        assert look.smooth == 0.3

    print("OK  LookController бере параметри активного профілю")


def test_profile_keys_switch_and_persist():

    with tempfile.TemporaryDirectory() as d:

        path = make_config(d, two_profiles())

        manager, look, osc, iface = build(path)

        assert iface.profile_name == "B"

        iface.handle_key(ord("p"))

        assert iface.profile_name == "A"
        assert look.horizontal_sensitivity_pct == 10.0
        assert look.smooth == 0.1
        assert osc.center_calls == 1

        with open(path, encoding="utf-8") as f:

            assert json.load(f)["active_profile"] == "A"

        iface.handle_key(ord("O"))

        assert iface.profile_name == "B"
        assert look.horizontal_sensitivity_pct == 40.0

    print("OK  клавіші P / O перемикають профіль і зберігають вибір")


def test_sensitivity_edits_go_to_their_profile():

    with tempfile.TemporaryDirectory() as d:

        path = make_config(d, two_profiles())

        manager, look, _osc, iface = build(path)

        # Профіль B: +2 до чутливості, потім перехід на A.
        iface.adjust_sensitivity("h", 1)

        assert look.horizontal_sensitivity_pct == 42.0

        iface.handle_key(ord("p"))

        assert look.horizontal_sensitivity_pct == 10.0

        with open(path, encoding="utf-8") as f:

            saved = json.load(f)

        by_name = {p["name"]: p for p in saved["profiles"]}

        assert by_name["B"]["horizontal_sensitivity_pct"] == 42.0
        assert by_name["A"]["horizontal_sensitivity_pct"] == 10.0

    print("OK  правка чутливості потрапляє у свій профіль, а не в сусідній")


def test_single_profile_and_no_profiles():

    with tempfile.TemporaryDirectory() as d:

        path = make_config(d, {"profiles": [{"name": "Only"}]})

        _manager, _look, osc, iface = build(path)

        assert iface.switch_profile(1) == "Only"
        assert osc.center_calls == 0

    # Interface без менеджера профілів (як у старих тестах).
    iface = Interface(FakeCalibration(), object(), FakeOsc())

    assert iface.profile_name is None
    assert iface.switch_profile(1) is None
    assert iface.handle_key(ord("p")) is False
    assert iface.save_settings() is False

    print("OK  один профіль / без профілів - перемикання нічого не ламає")


def test_status_shows_profile_name():

    with tempfile.TemporaryDirectory() as d:

        _manager, _look, _osc, iface = build(make_config(d, two_profiles()))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        iface.draw_status(frame)

        # Калібрування готове (FakeCalibration), тож малюється лише назва.
        assert frame[:30].max() > 0
        assert frame[40:].max() == 0

    print("OK  назва профілю показується у верхньому рядку кадру")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    print("------------------------------------")
    print("profiles.py checks")
    print("------------------------------------")

    test_loads_profiles_and_active()
    test_legacy_var_settings_becomes_default_profile()
    test_missing_or_broken_file_falls_back()
    test_duplicate_and_unknown_active()
    test_switch_wraps_around()
    test_save_keeps_other_keys_and_drops_var_settings()
    test_save_does_not_overwrite_unreadable_file()
    test_look_controller_uses_active_profile()
    test_profile_keys_switch_and_persist()
    test_sensitivity_edits_go_to_their_profile()
    test_single_profile_and_no_profiles()
    test_status_shows_profile_name()

    print("------------------------------------")
    print("All checks passed.")
