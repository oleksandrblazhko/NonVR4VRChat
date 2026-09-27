"""
test_camera_reader.py

Перевірка вибору камери з config.json (camera_reader.py):

    python -m pytest test_camera_reader.py
    python test_camera_reader.py

Справжня камера не відкривається: перевіряється лише функція
`load_camera_index()`, а `config.json` для неї створюється у
тимчасовому каталозі.
"""

from __future__ import annotations

import inspect
import io
import contextlib
import json
import os
import shutil
import tempfile

import camera_reader as camera_reader_mod

from camera_reader import CameraReader, load_camera_index


# ============================================================
# Helpers
# ============================================================

def capture(function, *args, **kwargs):
    """
    Повертає (вивід у консоль, результат виклику).
    """

    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):

        result = function(*args, **kwargs)

    return buffer.getvalue(), result


def read_index(payload):
    """
    Що поверне load_camera_index() для config.json з вмістом payload
    (None — файлу немає зовсім).
    """

    directory = tempfile.mkdtemp(prefix="mp_cam_")

    if payload is not None:

        with open(os.path.join(directory, "config.json"), "w", encoding="utf-8") as f:

            f.write(payload)

    saved = camera_reader_mod.__file__

    camera_reader_mod.__file__ = os.path.join(directory, "camera_reader.py")

    try:

        text, value = capture(load_camera_index)

    finally:

        camera_reader_mod.__file__ = saved

        shutil.rmtree(directory)

    return text, value


# ============================================================
# load_camera_index
# ============================================================

def test_index_from_config():

    for payload, expected in (
        ('{"camera_index": 0}', 0),
        ('{"camera_index": 1}', 1),
        ('{"camera_index": 2}', 2),
        ('{"camera_index": "3"}', 3),
    ):

        _text, value = read_index(payload)

        assert value == expected, payload

    print("OK  camera_index читається з config.json")


def test_index_defaults_when_missing():

    for payload in (None, "{}", '{"camera_index": null}'):

        _text, value = read_index(payload)

        assert value == 0, payload

    print("OK  без ключа (або без файла) - камера 0")


def test_index_defaults_on_broken_values():

    for payload in ('{"camera_index": "abc"}', '{"camera_index": tru', "[]"):

        _text, value = read_index(payload)

        assert value == 0, payload

    print("OK  битий JSON або не число - камера 0, без винятку")


def test_index_reported_on_error():

    text, value = read_index(None)

    # Мовчазний fallback замість рядка помилки - це пастка: програма
    # крутиться з не тією камерою, і користувач не знає чому.
    assert "Error loading config.json" in text

    assert value == 0

    print("OK  відсутній config.json позначається в консолі")


def test_index_matches_project_config():

    real = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "config.json"
    )

    with open(real, "r", encoding="utf-8") as f:

        expected = int(json.load(f)["camera_index"])

    _text, value = capture(load_camera_index)

    assert value == expected

    print("OK  load_camera_index() збігається з поточним config.json")


def test_constructor_uses_config_by_default():

    default = inspect.signature(CameraReader.__init__).parameters["camera_index"].default

    assert default is None

    print("OK  CameraReader() без аргументу - значення з config.json")


# ============================================================
# wait_first_frame
# ============================================================

class StubCapture:

    def __init__(self, opened=True):

        self.opened = opened

    def isOpened(self):

        return self.opened


class FakeReader(CameraReader):
    """
    CameraReader без заліза: read() видає заздалегідь підготовлену
    послідовність, тому очікування першого кадру перевіряється швидко
    і детерміновано.
    """

    def __init__(self, results, opened=True, camera_index=3):

        self.camera_index = camera_index

        self.camera = StubCapture(opened)

        self._results = list(results)

        self.reads = 0

    def read(self):

        self.reads += 1

        if self._results:

            return self._results.pop(0)

        return False, None


def test_wait_first_frame_returns_the_frame():

    reader = FakeReader([(False, None)] * 3 + [(True, "frame")])

    text, result = capture(

        reader.wait_first_frame,

        warn_after=1000.0,

        poll_interval=0.0

    )

    assert result == (True, "frame")

    assert reader.reads == 4

    # Кадр прийшов миттєво - жодного попередження.
    assert text == ""

    print("OK  wait_first_frame повертає перший успішний кадр")


def test_wait_first_frame_warns_about_camera():

    reader = FakeReader([(False, None)] * 3 + [(True, "frame")])

    text, _result = capture(

        reader.wait_first_frame,

        warn_after=0.0,

        poll_interval=0.0

    )

    assert text.count("Камера 3 кадрів не дає") == 3

    assert "camera_index у config.json" in text

    print("OK  без кадру є попередження з номером камери і порадою")


def test_wait_first_frame_distinguishes_closed_device():

    reader = FakeReader(

        [(False, None)] * 2 + [(True, "frame")],

        opened=False

    )

    text, _result = capture(

        reader.wait_first_frame,

        warn_after=0.0,

        poll_interval=0.0

    )

    assert "не відкрилась" in text

    assert "кадрів не дає" not in text

    print("OK  не відкритий пристрій відрізняється від «немає кадрів»")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    print("------------------------------------")
    print("camera_reader.py checks")
    print("------------------------------------")

    test_index_from_config()
    test_index_defaults_when_missing()
    test_index_defaults_on_broken_values()
    test_index_reported_on_error()
    test_index_matches_project_config()
    test_constructor_uses_config_by_default()
    test_wait_first_frame_returns_the_frame()
    test_wait_first_frame_warns_about_camera()
    test_wait_first_frame_distinguishes_closed_device()

    print("------------------------------------")
    print("All checks passed.")
