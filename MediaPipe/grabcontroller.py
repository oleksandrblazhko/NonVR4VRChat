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
    """
    Ліва кисть надсилає /input/UseRight коротким імпульсом.

    На відміну від хапка це не стан, а подія: `1` тримається
    `USE_PRESS_SECONDS`, після чого надсилається `0`. Наступний імпульс
    можливий лише після того, як рука зникне з кадру `HIDDEN_THRESHOLD`
    кадрів поспіль - інакше просто стояння з піднятою рукою сипало б
    дію предмета без зупину.
    """

    def __init__(self, osc_sender, press_seconds: float = 0.1):

        self.osc_sender = osc_sender

        self.VISIBLE_THRESHOLD = 1
        self.HIDDEN_THRESHOLD = 3
        self.VISIBILITY_LIMIT = 0.7
        self.USE_PRESS_SECONDS = press_seconds

        self.visible_counter = 0
        self.hidden_counter = 0

        # Готовий до наступного жесту.
        self.armed = True

        self.press_thread = None

    def update(self, left_wrist_landmark):

        if left_wrist_landmark is None:
            hand_visible = False
        else:
            hand_visible = left_wrist_landmark.visibility >= self.VISIBILITY_LIMIT

        if hand_visible:
            self.visible_counter += 1
            self.hidden_counter = 0
        else:
            self.hidden_counter += 1
            self.visible_counter = 0

        if self.armed and self.visible_counter >= self.VISIBLE_THRESHOLD:

            self.armed = False

            self.visible_counter = 0

            self._press()

        if self.hidden_counter >= self.HIDDEN_THRESHOLD:

            self.armed = True

            self.hidden_counter = 0

    def _press(self):

        self.press_thread = threading.Thread(
            target=self._press_cycle
        )

        self.press_thread.daemon = True

        self.press_thread.start()

    def _press_cycle(self):

        self.osc_sender.send_use_right(True)

        if self.osc_sender.debug:
            print("Action: Use")

        time.sleep(self.USE_PRESS_SECONDS)

        self.osc_sender.send_use_right(False)
