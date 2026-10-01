import subprocess


class VRChat:
    def __init__(self, executable):
        self.executable = executable

    def launch_world(self, world_id):
        self.close()

        url = f"vrchat://launch?id={world_id}"

        command = [
            self.executable,
            "--no-vr",
            "--url",
            url
        ]

        subprocess.Popen(command)

    def close(self):
        subprocess.run(
            ["taskkill", "/IM", "VRChat.exe", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
