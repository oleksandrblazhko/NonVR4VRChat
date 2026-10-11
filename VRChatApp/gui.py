import queue
import time
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from PIL import Image, ImageTk

from vrchat import VRChat
from status import StatusMonitor, OK, WAIT, OFF, UNKNOWN, KEYS

# Програми, які запускає start.bat (а не цей лаунчер). Для них монітор
# показує підказки, якщо вони не відповідають. Якщо камера або телефон
# не використовуються, приберіть відповідний ключ зі списку.
ASSUME_RUNNING = ("camera", "phone")

# Кольори індикаторів і підписи
LEVEL_COLORS = {
    OK: "#4CAF50",
    WAIT: "#FFC107",
    OFF: "#F44336",
    UNKNOWN: "#9E9E9E",
}

INDICATOR_NAMES = {
    "vrchat": "VRChat",
    "camera": "Камера",
    "phone": "Телефон",
    "osc": "OSC",
}

LOG_COLORS = {
    "info": "#222222",
    "warn": "#E65100",
    "error": "#B71C1C",
}


class VRChatLauncher:
    def __init__(self, root, config):
        self.root = root
        self.config = config

        self.root.title(config["application"]["title"])

        self.vrchat = VRChat(
            config["application"]["vrchat_executable"]
        )

        self.images = []

        # Черга для журналу (з неї читає лише GUI-потік)
        self.log_queue = queue.Queue()

        # Рядок індикаторів і підказка зверху (рядки 0-1)
        self.create_status_bar()

        # Світи починаються з рядка 2
        self.create_world_grid()

        # Журнал під сіткою світів
        self.create_log_panel()

        smartphone_config = (
            Path(__file__).resolve().parent.parent
            / "SmartPhone" / "config.json"
        )

        self.monitor = StatusMonitor(
            log=self.log,
            phone_config_path=smartphone_config,
            assume_launched=ASSUME_RUNNING,
        )
        self.monitor.start()

        self.log("Лаунчер запущено")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(500, self.poll)

    # ------------------------------------------------------------
    # Світи
    # ------------------------------------------------------------

    def create_world_grid(self):
        app_dir = Path(__file__).resolve().parent

        worlds = self.config["worlds"]

        # Рядок, з якого починається журнал
        self.log_row = 2 + (len(worlds) + 1) // 2

        for index, world in enumerate(worlds):
            # матриця 2x2 розташування кнопок-зображень світів
            # (рядки 0-1 зайняті індикаторами та підказкою)
            row = 2 + index // 2
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
                font=("Arial", 16, "bold")
            )
            name.pack()

            image_path = app_dir / world["image"]

            image = Image.open(image_path)
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
        self.log(f"Запуск світу: {world['name']}")

        try:
            self.vrchat.launch_world(world["id"])
        except OSError as e:
            self.log(f"Не вдалося запустити VRChat: {e}", "error")
            self.toggle_log(True)
            messagebox.showerror(
                "VRChat не знайдено",
                "Не вдалося запустити VRChat:\n"
                f"{self.config['application']['vrchat_executable']}\n\n"
                "Перевірте шлях vrchat_executable у VRChatApp/config.json.\n\n"
                f"Деталі: {e}",
                parent=self.root
            )

    # ------------------------------------------------------------
    # Індикатори
    # ------------------------------------------------------------

    def create_status_bar(self):
        bar = tk.Frame(self.root, pady=8)
        bar.grid(row=0, column=0, columnspan=2)

        self.indicator_dots = {}
        self.indicator_texts = {}

        for key in KEYS:
            block = tk.Frame(bar, padx=12)
            block.pack(side=tk.LEFT)

            top = tk.Frame(block)
            top.pack()

            dot = tk.Label(
                top, text="●", font=("Arial", 14),
                fg=LEVEL_COLORS[UNKNOWN], cursor="hand2"
            )
            dot.pack(side=tk.LEFT)

            name = tk.Label(
                top, text=INDICATOR_NAMES[key],
                font=("Arial", 11, "bold"), cursor="hand2"
            )
            name.pack(side=tk.LEFT, padx=(2, 0))

            detail = tk.Label(
                block, text="перевірка...",
                font=("Arial", 8), fg="#757575",
                wraplength=130, cursor="hand2"
            )
            detail.pack()

            # Клік по індикатору відкриває журнал
            for widget in (dot, name, detail):
                widget.bind("<Button-1>", lambda e: self.toggle_log(True))

            self.indicator_dots[key] = dot
            self.indicator_texts[key] = detail

        self.hint_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 10),
            fg="#B71C1C",
            bg="#FFF3E0",
            justify="left",
            anchor="w",
            wraplength=520,
            padx=10,
            pady=6
        )
        self.hint_label.grid(
            row=1, column=0, columnspan=2,
            sticky="we", padx=12, pady=(0, 6)
        )
        # Підказка видна лише коли є проблема
        self.hint_label.grid_remove()

    def poll(self):
        """Раз на 0,5 с: журнал, індикатори, підказка."""

        # 1. Журнал
        try:
            while True:
                stamp, text, level = self.log_queue.get_nowait()
                self._append_log(stamp, text, level)
        except queue.Empty:
            pass

        # 2. Індикатори
        snapshot = self.monitor.snapshot()

        for key in KEYS:
            status = snapshot[key]
            self.indicator_dots[key].config(fg=LEVEL_COLORS[status.level])
            self.indicator_texts[key].config(text=status.text)

        # 3. Підказка
        hints = self.monitor.hints()

        if hints:
            self.hint_label.config(
                text="⚠ " + "\n⚠ ".join(hints[:3])
            )
            self.hint_label.grid()
        else:
            self.hint_label.grid_remove()

        self.root.after(500, self.poll)

    def on_close(self):
        self.monitor.stop()
        self.root.destroy()

    # ------------------------------------------------------------
    # Журнал
    # ------------------------------------------------------------

    def log(self, text, level="info"):
        """Додати рядок у журнал. Безпечно викликати з будь-якого потоку."""
        self.log_queue.put((time.strftime("%H:%M:%S"), text, level))

    def create_log_panel(self):
        self.log_visible = False

        self.log_toggle = tk.Label(
            self.root,
            text="▸ Журнал",
            font=("Arial", 10, "bold"),
            fg="#455A64",
            cursor="hand2",
            anchor="w"
        )
        self.log_toggle.grid(
            row=self.log_row, column=0, columnspan=2,
            sticky="we", padx=12, pady=(0, 4)
        )
        self.log_toggle.bind("<Button-1>", lambda e: self.toggle_log())

        self.log_frame = tk.Frame(self.root)
        self.log_frame.grid(
            row=self.log_row + 1, column=0, columnspan=2,
            sticky="we", padx=12, pady=(0, 10)
        )

        self.log_text = tk.Text(
            self.log_frame,
            height=8,
            width=72,
            font=("Consolas", 9),
            state="disabled",
            wrap="word"
        )
        scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        for level, color in LOG_COLORS.items():
            self.log_text.tag_configure(level, foreground=color)
        self.log_text.tag_configure("time", foreground="#9E9E9E")

        # Журнал згорнутий за замовчуванням
        self.log_frame.grid_remove()

    def toggle_log(self, show=None):
        if show is None:
            show = not self.log_visible

        self.log_visible = show

        if show:
            self.log_frame.grid()
            self.log_toggle.config(text="▾ Журнал")
            self.log_text.see("end")
        else:
            self.log_frame.grid_remove()
            self.log_toggle.config(text="▸ Журнал")

    def _append_log(self, stamp, text, level):
        self.log_text.config(state="normal")
        self.log_text.insert("end", stamp + "  ", "time")
        self.log_text.insert("end", text + "\n", level)
        self.log_text.config(state="disabled")
        self.log_text.see("end")
