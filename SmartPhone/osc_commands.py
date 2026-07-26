# TurboScratch/osc_commands.py

from pythonosc import udp_client

OSC_IP = "127.0.0.1"
OSC_PORT = 9000

class OSCCommands:
    def __init__(self, debug=False, osc_bindings=[]):
        self.client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
        self.debug = debug
        self.osc_bindings = osc_bindings
        self._pressed = {binding["osc_command"]: False for binding in osc_bindings}
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

    def send_commands(self, accX, accY, accZ, offset_accX, offset_accY, offset_accZ, threshold=0.5, run_threshold=1.5):
        """
        Sends OSC commands based on phone tilt, using configurable bindings.
        """
        dx = accX - offset_accX
        dy = accY - offset_accY
        dz = accZ - offset_accZ # Not used in current bindings, but available

        for binding in self.osc_bindings:
            command = binding["osc_command"]
            axis = binding["axis"]
            active = False

            if command == "/input/MoveForward":
                if axis == "X" and dx > threshold:
                    active = True
            elif command == "/input/MoveBackward":
                if axis == "X" and dx < -threshold:
                    active = True
            elif command == "/input/MoveLeft":
                if axis == "Y" and dy < -threshold:
                    active = True
            elif command == "/input/MoveRight":
                if axis == "Y" and dy > threshold:
                    active = True
            elif command == "/input/Run":
                if axis == "X_Y" and (abs(dx) > run_threshold or abs(dy) > run_threshold):
                    active = True
            
            # Additional logic can be added here for other commands and axes
            # For example, using the Z-axis:
            # elif command == "/input/Jump":
            #     if axis == "Z" and dz > some_z_threshold:
            #         active = True

            self._set_command(command, active)
