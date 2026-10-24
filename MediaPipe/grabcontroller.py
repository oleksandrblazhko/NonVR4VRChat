"""
grabcontroller.py

Жести кистей у команди VRChat:

    права кисть  -> /input/GrabRight (хапок, поки кисть у кадрі)
    ліва кисть   -> /input/UseRight  (дія предмета, короткий імпульс)
"""

import time
import threading


class GrabController:
    def __init__(self, osc_sender):
        self.osc_sender = osc_sender
        self.grab_state = False
        self.visible_counter = 0
        self.hidden_counter = 0

        self.VISIBLE_THRESHOLD = 1
        self.HIDDEN_THRESHOLD = 3
        self.VISIBILITY_LIMIT = 0.7

    def update(self, right_wrist_landmark):
        if right_wrist_landmark is None:
            hand_visible = False
        else:
            hand_visible = right_wrist_landmark.visibility >= self.VISIBILITY_LIMIT

        if hand_visible:
            self.visible_counter += 1
            self.hidden_counter = 0
        else:
            self.hidden_counter += 1
            self.visible_counter = 0

        # Grab
        if not self.grab_state and self.visible_counter >= self.VISIBLE_THRESHOLD:
            self.osc_sender.send_grab_right(True)
            self.grab_state = True
            self.visible_counter = 0
            self.hidden_counter = 0
            if self.osc_sender.debug:
                print("Action: Grab")

        # Drop
        elif self.grab_state and self.hidden_counter >= self.HIDDEN_THRESHOLD:
            self.osc_sender.send_grab_right(False)
            self.grab_state = False
            self.visible_counter = 0
            self.hidden_counter = 0
            if self.osc_sender.debug:
                print("Action: Drop")


class UseController:
    def __init__(self, osc_sender, press_seconds: float = 0.15):
        self.osc_sender = osc_sender

        self.VISIBLE_THRESHOLD = 1
        self.HIDDEN_THRESHOLD = 3
        self.VISIBILITY_LIMIT = 0.7
        self.USE_PRESS_SECONDS = press_seconds

        self.visible_counter = 0
        self.hidden_counter = 0
        self.armed = True
        self.last_triggered_time = 0.0

    @property
    def is_triggered(self) -> bool:
        return (time.time() - self.last_triggered_time) < 0.4

    def update(self, left_wrist_landmark):
        if left_wrist_landmark is None:
            hand_visible = False
        else:
            hand_visible = left_wrist_landmark.visibility >= self.VISIBILITY_LIMIT
        self.update_active(hand_visible)

    def update_active(self, hand_visible: bool):
        if hand_visible:
            self.visible_counter += 1
            self.hidden_counter = 0
        else:
            self.hidden_counter += 1
            self.visible_counter = 0

        if self.armed and self.visible_counter >= self.VISIBLE_THRESHOLD:
            self.armed = False
            self.visible_counter = 0
            threading.Thread(target=self._press_cycle, daemon=True).start()

        if self.hidden_counter >= self.HIDDEN_THRESHOLD:
            self.armed = True
            self.hidden_counter = 0

    def _press_cycle(self):
        self.last_triggered_time = time.time()
        self.osc_sender.send_drop_right(True)
        if self.osc_sender.debug:
            print("Action: Use")
        time.sleep(self.USE_PRESS_SECONDS)
        self.osc_sender.send_drop_right(False)
