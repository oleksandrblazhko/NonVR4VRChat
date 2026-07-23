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
            print("Action: Grab")

        # Drop
        elif self.grab_state and self.hidden_counter >= self.HIDDEN_THRESHOLD:
            self.osc_sender.send_grab_right(False)
            self.grab_state = False
            self.visible_counter = 0
            self.hidden_counter = 0
            print("Action: Drop")