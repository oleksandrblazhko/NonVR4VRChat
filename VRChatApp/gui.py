import json
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

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
            font=("Arial", 16, "bold"),
            bg="#4CAF50",
            fg="white",
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.launch_mediapipe
        )
        btn_mediapipe.pack(side=tk.LEFT, padx=9)

        # Кнопка запуску SmartPhone
        btn_smartphone = tk.Button(
            controls_frame,
            text="Навігація руху",
            font=("Arial", 16, "bold"),
            bg="#2196F3",
            fg="white",
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.launch_smartphone
        )
        btn_smartphone.pack(side=tk.LEFT, padx=15)

        #Меню налаштувань
        btn_settings = tk.Button(
            controls_frame,
            text="Налаштування",
            font=("Arial", 16, "bold"),
            bg="#607D8B",
            fg="white",
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.open_settings
        )
        btn_settings.pack(side=tk.LEFT, padx=15)

    def open_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Налаштування")
        settings_window.geometry("380x180")
        settings_window.resizable(False, False)

        #Шлях до файлу config.json
        smartphone_config_path = Path(__file__).resolve().parent.parent / "SmartPhone" / "config.json"

        #Зчитування поточного IP
        current_ip = "192.168.0.100"
        if smartphone_config_path.exists():
            try:
                with open(smartphone_config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    current_ip = data.get("server_ip", current_ip)
            except Exception:
                pass

        label = tk.Label(
            settings_window,
            text="IP-адреса телефону:",
            font=("Arial", 12, "bold")
        )
        label.pack(pady=(20, 5))

        ip_entry = tk.Entry(settings_window, font=("Arial", 12), justify="center", width=25)
        ip_entry.insert(0, current_ip)
        ip_entry.pack(pady=5)

        def save_ip():
            new_ip = ip_entry.get().strip()
            if not new_ip:
                messagebox.showwarning("Помилка", "IP-адреса не може бути порожньою!", parent=settings_window)
                return

            if smartphone_config_path.exists():
                try:
                    with open(smartphone_config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    data["server_ip"] = new_ip

                    with open(smartphone_config_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    messagebox.showinfo("Успіх", "IP-адресу успішно оновлено!", parent=settings_window)
                    settings_window.destroy()
                except Exception as e:
                    messagebox.showerror("Помилка", f"Не вдалося зберегти файл: {e}", parent=settings_window)
            else:
                messagebox.showerror("Помилка", f"Файл не знайдено: {smartphone_config_path}", parent=settings_window)

        btn_save = tk.Button(
            settings_window,
            text="Зберегти",
            font=("Arial", 16, "bold"),
            bg="#4CAF50",
            fg="white",
            padx=10,
            pady=4,
            cursor="hand2",
            command=save_ip
        )
        btn_save.pack(pady=15)

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