import tkinter as tk
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

    def create_world_grid(self):
        for index, world in enumerate(self.config["worlds"]):
            row = index // 3
            column = index % 3

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
                text=world["name"]
            )
            name.pack()

            image = Image.open(world["image"])
            image = image.resize((250, 150))
            photo = ImageTk.PhotoImage(image)

            # Зберігаємо посилання на зображення,
            # щоб Tkinter не видалив його з пам'яті.
            self.images.append(photo)

            image_label = tk.Label(
                frame,
                image=photo,
                cursor="hand2"
            )
            image_label.pack()

            # Клікабельне лише зображення.
            image_label.bind(
                "<Button-1>",
                lambda event, world=world:
                    self.world_clicked(world)
            )

    def world_clicked(self, world):
        self.vrchat.launch_world(world["id"])
        