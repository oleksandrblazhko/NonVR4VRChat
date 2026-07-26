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
        if command not in self._pressed:
            return # Ignore commands not in the bindings

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

    def send_commands(self, accX, accY, accZ, offset_accX, offset_accY, offset_accZ, move_threshold=0.5, run_threshold=1.5):
        """
        Sends OSC commands based on phone tilt, using configurable bindings.
        """
        deltas = {
            "X": accX - offset_accX,
            "Y": accY - offset_accY,
            "Z": accZ - offset_accZ
        }

        command_active = {binding["osc_command"]: False for binding in self.osc_bindings}

        for binding in self.osc_bindings:
            command = binding["osc_command"]
            axis = binding["axis"]
            invert = binding.get("invert", False) # Get invert property, defaults to False

            value = deltas.get(axis)
            
            # Apply inversion only to directional commands
            if command in ["/input/MoveForward", "/input/MoveBackward", "/input/MoveLeft", "/input/MoveRight"]:
                if value is not None and invert:
                    value = -value

            is_active = False
            if command == "/input/MoveForward":
                if value is not None:
                    is_active = value > move_threshold
            elif command == "/input/MoveBackward":
                if value is not None:
                    is_active = value < -move_threshold
            elif command == "/input/MoveLeft":
                if value is not None:
                    is_active = value < -move_threshold
            elif command == "/input/MoveRight":
                if value is not None:
                    is_active = value > move_threshold
            elif command == "/input/Run":
                axes_for_run = axis.split('_')
                is_running = False
                for run_axis in axes_for_run:
                    # Inversion does not apply to /input/Run as it checks absolute magnitude
                    if abs(deltas.get(run_axis, 0)) > run_threshold:
                        is_running = True
                        break
                is_active = is_running

            if is_active:
                command_active[command] = True
        
        # To prevent sending both forward and backward, or left and right at the same time
        if command_active.get("/input/MoveForward", False) and command_active.get("/input/MoveBackward", False):
             command_active["/input/MoveForward"] = False
             command_active["/input/MoveBackward"] = False

        if command_active.get("/input/MoveLeft", False) and command_active.get("/input/MoveRight", False):
             command_active["/input/MoveLeft"] = False
             command_active["/input/MoveRight"] = False

        # Send commands
        for command in self._pressed:
            self._set_command(command, command_active.get(command, False))

        # Example for other commands
        # for binding in self.osc_bindings:
        #     command = binding["osc_command"]
        #     axis = binding["axis"]
        #     if command == "/input/Jump":
        #         if axis == "Z" and dz > some_z_threshold:
        #             self._set_command(command, True)
        #         else:
        #             self._set_command(command, False)
