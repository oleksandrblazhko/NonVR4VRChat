import pydirectinput

# ---------------------------------------------------------
# Поточний стан клавіш
# ---------------------------------------------------------

_pressed = {
    "w": False,
    "a": False,
    "s": False,
    "d": False,
}


def _set_key(key: str, pressed: bool):
    """
    Натискає або відпускає клавішу лише тоді,
    коли її стан змінився.
    """

    global _pressed

    if pressed:

        if not _pressed[key]:
            pydirectinput.keyDown(key)
            _pressed[key] = True

    else:

        if _pressed[key]:
            pydirectinput.keyUp(key)
            _pressed[key] = False


def release_all_keys():
    """
    Відпустити всі клавіші.
    Викликати при завершенні програми.
    """

    for key in _pressed:
        _set_key(key, False)


def press_keys(
    accX,
    accY,
    offset_accX,
    offset_accY,
    threshold=0.5,
):
    """
    Керує клавішами WASD залежно від нахилу смартфона.

    Parameters
    ----------
    accX, accY
        Поточні значення акселерометра.

    offset_accX, offset_accY
        Значення акселерометра у стані спокою.

    threshold
        Мінімальне відхилення для спрацьовування.
    """

    dx = accX - offset_accX
    dy = accY - offset_accY

    # -------------------------
    # X
    # -------------------------

    if dx > threshold:

        _set_key("w", True)
        _set_key("s", False)

    elif dx < -threshold:

        _set_key("s", True)
        _set_key("w", False)

    else:

        _set_key("w", False)
        _set_key("s", False)

    # -------------------------
    # Y
    # -------------------------

    if dy > threshold:

        _set_key("d", True)
        _set_key("a", False)

    elif dy < -threshold:

        _set_key("a", True)
        _set_key("d", False)

    else:

        _set_key("a", False)
        _set_key("d", False)