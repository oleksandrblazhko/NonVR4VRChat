import ctypes

import pydirectinput


def vrchat_focused() -> bool:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value == "VRChat"


class DirectInput:

    def __init__(self):

        self.VISIBLE_THRESHOLD = 1
        self.HIDDEN_THRESHOLD = 3
        self.VISIBILITY_LIMIT = 0.7

        self.visible_counter = 0
        self.hidden_counter = 0

        self.use_state = False

        self.press_thread = None
        self.last_triggered_time = 0.0

    def update(self, left_wrist_landmark):
        #print("at update start")
        if left_wrist_landmark is None:
            hand_visible = False
        else:
            hand_visible = left_wrist_landmark.visibility >= self.VISIBILITY_LIMIT

        if  hand_visible:
            self.hidden_counter = 0
            self.visible_counter += 1
        else:
            self.visible_counter = 0
            self.hidden_counter += 1

        # Charge
        if not self.use_state and self.visible_counter >= self.VISIBLE_THRESHOLD:
            if self.charge():
                self.use_state = True
            self.visible_counter = 0
            self.hidden_counter = 0

        # Throw
        elif self.use_state and self.hidden_counter >= self.HIDDEN_THRESHOLD:
            self.release()
            self.visible_counter = 0
            self.hidden_counter = 0

    def charge(self) -> bool:
        print("entered Charge")
        if not vrchat_focused():
             print("Vrchat nt focused")
             return False
        pydirectinput.mouseDown(button="right")
        print("Charging")
        return True

    def release(self):
        if not self.use_state:
            return
        pydirectinput.mouseUp(button="right")
        self.use_state = False
        self.visible_counter = 0
        self.hidden_counter = 0