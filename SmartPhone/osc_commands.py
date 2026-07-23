# TurboScratch/osc_commands.py

from pythonosc import udp_client

OSC_IP = "127.0.0.1"
OSC_PORT = 9000

class OSCCommands:
    def __init__(self, debug=False):
        self.client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
        self.debug = debug
        self._pressed = {
            "/input/MoveForward": False,
            "/input/MoveBackward": False,
            "/input/MoveLeft": False,
            "/input/MoveRight": False,
            "/input/Run": False,
        }
        print("OSC command sender initialized.")

    def _set_command(self, command: str, active: bool):
        """
        Sends an OSC command only when its state has changed.
        """
        if active:
            if not self._pressed.get(command, True):
                if self.debug:
                    print(f"OSC out: {command} -> {True}")
                self.client.send_message(command, True)
                self._pressed[command] = True
        else:
            if self._pressed.get(command, False):
                if self.debug:
                    print(f"OSC out: {command} -> {False}")
                self.client.send_message(command, False)
                self._pressed[command] = False

    def release_all_commands(self):
        """
        Sends messages to deactivate all commands.
        """
        print("Releasing all OSC commands...")
        for command in self._pressed:
            self._set_command(command, False)

    def send_commands(self, accX, accY, offset_accX, offset_accY, threshold=0.5, run_threshold=1.5):
        """
        Sends OSC commands based on phone tilt.
        """
        dx = accX - offset_accX
        dy = accY - offset_accY

        # Corresponds to 'w' (forward) and 's' (backward)
        if dx > threshold:
            self._set_command("/input/MoveForward", True)
            self._set_command("/input/MoveBackward", False)
        elif dx < -threshold:
            self._set_command("/input/MoveForward", False)
            self._set_command("/input/MoveBackward", True)
        else:
            self._set_command("/input/MoveForward", False)
            self._set_command("/input/MoveBackward", False)

        # Run command logic
        if dx > run_threshold or dx < -run_threshold: # Activate run for significant forward or backward tilt
            self._set_command("/input/Run", True)
        else:
            self._set_command("/input/Run", False)

        # Corresponds to 'd' (right) and 'a' (left)
        if dy > threshold:
            self._set_command("/input/MoveRight", True)
            self._set_command("/input/MoveLeft", False)
        elif dy < -threshold:
            self._set_command("/input/MoveRight", False)
            self._set_command("/input/MoveLeft", True)
        else:
            self._set_command("/input/MoveRight", False)
            self._set_command("/input/MoveLeft", False)
