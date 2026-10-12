import json
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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

        # Зберігання активних процесів для керування та зупинки
        self.process_mediapipe = None
        self.process_smartphone = None
        self.settings_window = None
        self.create_world_grid()

        # Панель внизу
        self.create_bottom_controls()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_world_grid(self):
        app_dir = Path(__file__).resolve().parent

        for index, world in enumerate(self.config["worlds"]):
            #Сітка 2х2
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

        #Кнопка запуску MediaPipe
        self.btn_mediapipe = tk.Button(
            controls_frame,
            text="Навігація веб-камера",
            font=("Arial", 16, "bold"),
            bg="#4CAF50",
            fg="white",
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.toggle_mediapipe
        )
        self.btn_mediapipe.pack(side=tk.LEFT, padx=9)

        #Кнопка запуску SmartPhone
        self.btn_smartphone = tk.Button(
            controls_frame,
            text="Навігація руху",
            font=("Arial", 16, "bold"),
            bg="#2196F3",
            fg="white",
            padx=8,
            pady=4,
            cursor="hand2",
            command=self.toggle_smartphone
        )
        self.btn_smartphone.pack(side=tk.LEFT, padx=15)

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

    def toggle_mediapipe(self):

        if self.process_mediapipe and self.process_mediapipe.poll() is None:
            self.process_mediapipe.terminate()
            self.process_mediapipe = None
        else:
            script_path = Path(__file__).resolve().parent.parent / "MediaPipe" / "main.py"
            self.process_mediapipe = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent)
            )

    def toggle_smartphone(self):
        if self.process_smartphone and self.process_smartphone.poll() is None:
            self.process_smartphone.terminate()
            self.process_smartphone = None
        else:
            script_path = Path(__file__).resolve().parent.parent / "SmartPhone" / "main.py"
            self.process_smartphone = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent)
            )

    def on_closing(self):
        #Закриття програми разом з головним меню
        if self.process_mediapipe and self.process_mediapipe.poll() is None:
            self.process_mediapipe.terminate()

        if self.process_smartphone and self.process_smartphone.poll() is None:
            self.process_smartphone.terminate()

        self.root.destroy()

    def open_settings(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
            self.settings_window = None
            return

        settings_window = tk.Toplevel(self.root)
        self.settings_window = settings_window
        settings_window.title("Налаштування")
        settings_window.geometry("540x480")
        settings_window.resizable(False, False)

        def on_settings_close():
            self.settings_window = None
            settings_window.destroy()

        settings_window.protocol("WM_DELETE_WINDOW", on_settings_close)

        # Шляхи до файлів конфігурацій
        app_dir = Path(__file__).resolve().parent
        vrchat_config_path = app_dir / "config.json"
        smartphone_config_path = app_dir.parent / "SmartPhone" / "config.json"

        # Пресети орієнтації та прив'язок OSC
        presets = {
            "1. В руках": [
                {"osc_command": "/input/MoveForward", "axis": "Z"},
                {"osc_command": "/input/MoveBackward", "axis": "Z"},
                {"osc_command": "/input/MoveLeft", "axis": "X"},
                {"osc_command": "/input/MoveRight", "axis": "X"},
                {"osc_command": "/input/Run", "axis": "X_Z"}
            ],
            "2. На дошці": [
                {"osc_command": "/input/MoveForward", "axis": "X"},
                {"osc_command": "/input/MoveBackward", "axis": "X"},
                {"osc_command": "/input/MoveLeft", "axis": "Y"},
                {"osc_command": "/input/MoveRight", "axis": "Y"},
                {"osc_command": "/input/Run", "axis": "X_Y"}
            ],
            "3. На нозі спереду": [
                {"osc_command": "/input/MoveForward", "axis": "X"},
                {"osc_command": "/input/MoveBackward", "axis": "X"},
                {"osc_command": "/input/MoveLeft", "axis": "Y", "invert": True},
                {"osc_command": "/input/MoveRight", "axis": "Y", "invert": True},
                {"osc_command": "/input/Run", "axis": "X_Y"}
            ]
        }

        # Налаштування кутів
        preset_thresholds = {
            "1. В руках": {"move": 5.0, "run": 10.0},
            "2. На дошці": {"move": 5.0, "run": 10.0},
            "3. На нозі спереду": {"move": 5.0, "run": 10.0}
        }

        current_ip = "192.168.0.100"
        current_bindings = []

        if smartphone_config_path.exists():
            try:
                with open(smartphone_config_path, "r", encoding="utf-8") as f:
                    phone_data = json.load(f)
                    current_ip = phone_data.get("server_ip", current_ip)
                    current_bindings = phone_data.get("osc_bindings", [])

                    #Індивідуальні пресети
                    saved_preset_thresh = phone_data.get("preset_thresholds", {})
                    for p_name, t_val in saved_preset_thresh.items():
                        if p_name in preset_thresholds:
                            preset_thresholds[p_name] = t_val

                    current_thresh = phone_data.get("thresholds", {})
                    if "move" in current_thresh and "run" in current_thresh:
                        #Поточний поріг в активний пресет
                        for name, bindings in presets.items():
                            if current_bindings == bindings:
                                preset_thresholds[name] = {
                                    "move": float(current_thresh["move"]),
                                    "run": float(current_thresh["run"])
                                }
                                break
            except Exception:
                pass

        #Вибраний пресет
        selected_preset_name = list(presets.keys())[0]
        for name, bindings in presets.items():
            if current_bindings == bindings:
                selected_preset_name = name
                break

        current_active_preset = [selected_preset_name]

        current_vrchat_path = self.config.get("application", {}).get(
            "vrchat_executable", ""
        )

        #IP-адреса телефону
        lbl_ip = tk.Label(
            settings_window,
            text="IP-адреса телефону:",
            font=("Arial", 10, "bold")
        )
        lbl_ip.pack(anchor="w", padx=20, pady=(12, 2))

        ip_entry = tk.Entry(settings_window, font=("Arial", 10))
        ip_entry.insert(0, current_ip)
        ip_entry.pack(fill="x", padx=20, pady=(0, 8))

        #Пресет
        lbl_preset = tk.Label(
            settings_window,
            text="Розташування смартфону:",
            font=("Arial", 10, "bold")
        )
        lbl_preset.pack(anchor="w", padx=20, pady=(5, 2))

        preset_combobox = ttk.Combobox(
            settings_window,
            values=list(presets.keys()),
            state="readonly",
            font=("Arial", 9)
        )
        preset_combobox.set(selected_preset_name)
        preset_combobox.pack(fill="x", padx=20, pady=(0, 8))

        #Кут нахилу
        lbl_thresholds = tk.Label(
            settings_window,
            text="Значення кута нахилу:",
            font=("Arial", 10, "bold")
        )
        lbl_thresholds.pack(anchor="w", padx=20, pady=(5, 2))

        thresh_frame = tk.Frame(settings_window)
        thresh_frame.pack(fill="x", padx=20, pady=(0, 8))

        tk.Label(thresh_frame, text="Ходьба:", font=("Arial", 9)).grid(row=0, column=0, sticky="w", padx=(0, 5))
        move_entry = tk.Entry(thresh_frame, font=("Arial", 9), width=10)
        move_entry.insert(0, str(preset_thresholds[selected_preset_name]["move"]))
        move_entry.grid(row=0, column=1, padx=(0, 20))

        tk.Label(thresh_frame, text="Біг:", font=("Arial", 9)).grid(row=0, column=2, sticky="w", padx=(0, 5))
        run_entry = tk.Entry(thresh_frame, font=("Arial", 9), width=10)
        run_entry.insert(0, str(preset_thresholds[selected_preset_name]["run"]))
        run_entry.grid(row=0, column=3)

        #Автоматична зміна кутів
        def on_preset_changed(event=None):
            prev_name = current_active_preset[0]
            try:
                m_val = float(move_entry.get().strip())
                r_val = float(run_entry.get().strip())
                preset_thresholds[prev_name] = {"move": m_val, "run": r_val}
            except ValueError:
                pass

            new_name = preset_combobox.get()
            current_active_preset[0] = new_name
            target_vals = preset_thresholds.get(new_name, {"move": 5.0, "run": 10.0})

            move_entry.delete(0, tk.END)
            move_entry.insert(0, str(target_vals["move"]))

            run_entry.delete(0, tk.END)
            run_entry.insert(0, str(target_vals["run"]))

        preset_combobox.bind("<<ComboboxSelected>>", on_preset_changed)

        #Шлях до VRChat
        lbl_path = tk.Label(
            settings_window,
            text="Шлях до VRChat:",
            font=("Arial", 10, "bold")
        )
        lbl_path.pack(anchor="w", padx=20, pady=(5, 2))

        path_frame = tk.Frame(settings_window)
        path_frame.pack(fill="x", padx=20, pady=(0, 15))

        path_entry = tk.Entry(path_frame, font=("Arial", 10))
        path_entry.insert(0, current_vrchat_path)
        path_entry.pack(side=tk.LEFT, fill="x", expand=True)

        def browse_file():
            selected_file = filedialog.askopenfilename(
                title="Оберіть launch.exe VRChat",
                filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
                parent=settings_window
            )
            if selected_file:
                path_entry.delete(0, tk.END)
                path_entry.insert(0, selected_file.replace("/", "\\"))

        btn_browse = tk.Button(
            path_frame,
            text="Огляд...",
            font=("Arial", 9),
            command=browse_file,
            cursor="hand2"
        )
        btn_browse.pack(side=tk.LEFT, padx=(5, 0))

        #Скидання
        def reset_defaults():
            current_mode = preset_combobox.get()
            preset_thresholds[current_mode] = {"move": 5.0, "run": 10.0}

            move_entry.delete(0, tk.END)
            move_entry.insert(0, "5.0")

            run_entry.delete(0, tk.END)
            run_entry.insert(0, "10.0")

            default_vrchat = r"C:\Windows\TempInst\Steam\steamapps\common\VRChat\launch.exe"
            path_entry.delete(0, tk.END)
            path_entry.insert(0, default_vrchat)

        bottom_btn_frame = tk.Frame(settings_window)
        bottom_btn_frame.pack(fill="x", padx=20, pady=(10, 5))

        btn_reset = tk.Button(
            bottom_btn_frame,
            text="Скинути за замовчуванням",
            font=("Arial", 10),
            bg="#9E9E9E",
            fg="white",
            padx=10,
            pady=4,
            cursor="hand2",
            command=reset_defaults
        )
        btn_reset.pack(side=tk.LEFT)

        def save_all():
            new_ip = ip_entry.get().strip()
            move_str = move_entry.get().strip()
            run_str = run_entry.get().strip()
            new_vrchat_path = path_entry.get().strip()
            selected_mode = preset_combobox.get()

            if not new_ip:
                messagebox.showwarning("Помилка", "IP-адреса не може бути порожньою!", parent=settings_window)
                return

            try:
                move_val = float(move_str)
                run_val = float(run_str)
            except ValueError:
                messagebox.showwarning("Помилка", "Значення кутів не можуть бути порожніми!", parent=settings_window)
                return

            if not new_vrchat_path:
                messagebox.showwarning("Помилка", "Шлях до VRChat не може бути порожнім!", parent=settings_window)
                return

            preset_thresholds[selected_mode] = {"move": move_val, "run": run_val}

            #Оновлення SmartPhone/config.json
            if smartphone_config_path.exists():
                try:
                    with open(smartphone_config_path, "r", encoding="utf-8") as f:
                        phone_data = json.load(f)

                    phone_data["server_ip"] = new_ip
                    if "thresholds" not in phone_data:
                        phone_data["thresholds"] = {}

                    phone_data["thresholds"]["move"] = move_val
                    phone_data["thresholds"]["run"] = run_val

                    phone_data["preset_thresholds"] = preset_thresholds

                    if selected_mode in presets:
                        phone_data["osc_bindings"] = presets[selected_mode]

                    with open(smartphone_config_path, "w", encoding="utf-8") as f:
                        json.dump(phone_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    messagebox.showerror("Помилка", f"Не вдалося оновити SmartPhone/config.json: {e}",
                                         parent=settings_window)
                    return
            else:
                messagebox.showerror("Помилка", f"Файл не знайдено: {smartphone_config_path}", parent=settings_window)
                return

            #Оновлення VRChatApp/config.json
            try:
                self.config["application"]["vrchat_executable"] = new_vrchat_path
                self.vrchat.executable = new_vrchat_path
                with open(vrchat_config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4, ensure_ascii=False)
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося оновити VRChatApp/config.json: {e}",
                                     parent=settings_window)
                return

            messagebox.showinfo("Успіх", "Налаштування успішно збережено!", parent=settings_window)
            settings_window.destroy()

        btn_save = tk.Button(
            bottom_btn_frame,
            text="Зберегти",
            font=("Arial", 11, "bold"),
            bg="#4CAF50",
            fg="white",
            padx=15,
            pady=4,
            cursor="hand2",
            command=save_all
        )
        btn_save.pack(side=tk.RIGHT)

    def world_clicked(self, world):
        self.vrchat.launch_world(world["id"])