import subprocess
import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from vrchat import VRChat


class VRChatLauncher:
    def __init__(self, root, config):
        self.root = root
        self.config = config

        self.root.title(config["application"]["title"])

        self.vrchat = VRChat(
            config["application"]["vrchat_executable"]
        )

        self.images = []

        self.create_world_grid()

        #Панель внизу
        self.create_bottom_controls()

    def create_world_grid(self):
        app_dir = Path(__file__).resolve().parent

        for index, world in enumerate(self.config["worlds"]):
            # Сітка 2х2
            row = index // 2
            column = index % 2

            frame = tk.Frame(
                self.root,
                padx=10,
                pady=10
            )
            frame.grid(
                row=row,
                column=column
            )

            name = tk.Label(
                frame,
                text=world["name"],
                font=("Arial", 10, "bold")
            )
            name.pack(pady=(0, 5))

            image_path = app_dir / world["image"]

            image = Image.open(image_path)
            image = image.resize((260, 150))
            photo = ImageTk.PhotoImage(image)

            # Зберігаємо посилання на зображення
            self.images.append(photo)

            image_label = tk.Label(
                frame,
                image=photo,
                cursor="hand2"
            )
            image_label.pack()

            # Клікабельне лише зображення
            image_label.bind(
                "<Button-1>",
                lambda event, world=world:
                    self.world_clicked(world)
            )

    def create_bottom_controls(self):
        controls_frame = tk.Frame(self.root, pady=15)
        controls_frame.grid(row=2, column=0, columnspan=2)

        # Кнопка запуску MediaPipe
        btn_mediapipe = tk.Button(
            controls_frame,
            text="Навігація веб-камера",
            font=("Arial", 10, "bold"),
            bg="#4CAF50",
            fg="white",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.launch_mediapipe
        )
        btn_mediapipe.pack(side=tk.LEFT, padx=15)

        # Кнопка запуску SmartPhone
        btn_smartphone = tk.Button(
            controls_frame,
            text="Навігація руху",
            font=("Arial", 10, "bold"),
            bg="#2196F3",
            fg="white",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.launch_smartphone
        )
        btn_smartphone.pack(side=tk.LEFT, padx=15)

    def world_clicked(self, world):
        self.vrchat.launch_world(world["id"])

    def launch_mediapipe(self):
        # Шлях до MediaPipe
        script_path = Path(__file__).resolve().parent.parent / "MediaPipe" / "main.py"
        subprocess.Popen([sys.executable, str(script_path)], cwd=str(script_path.parent))

    def launch_smartphone(self):
        # Шлях до SmartPhone
        script_path = Path(__file__).resolve().parent.parent / "SmartPhone" / "main.py"
        subprocess.Popen([sys.executable, str(script_path)], cwd=str(script_path.parent))