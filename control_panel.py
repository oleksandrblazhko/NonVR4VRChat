"""
control_panel.py

Єдина панель керування проєктом NonVR4VRChat.

Замість трьох окремих консолей з start.bat запускається одне маленьке вікно,
яке саме стартує та зупиняє компоненти (телефон, камера, лаунчер) і
реагує на глобальні гарячі клавіші - навіть коли у фокусі VRChat.

Клавіші та параметри компонентів - у control_panel.json.
Типово:

    F5  - телефон (SmartPhone)    вкл / викл
    F6  - камера  (MediaPipe)     вкл / викл
    F7  - лаунчер (VRChatApp)     вкл / викл
    F8  - ВСЕ: якщо щось працює - закрити все, інакше - запустити все

Запуск: start.bat (або `python control_panel.py`).

Важливо: при зупинці компонента панель відправляє у VRChat нейтральні OSC-
значення (рух, погляд, руки). Інакше після примусового закриття програми
аватар міг би «залипнути» й продовжити йти або крутитися.
"""

from __future__ import annotations

import json
import os
import queue
import signal
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path


# ============================================================
# Тексти інтерфейсу
# ============================================================

TITLE = "NonVR4VRChat - керування"

TXT_RUNNING = "працює"
TXT_STOPPED = "вимкнено"
TXT_EXITED_OK = "завершено"
TXT_EXITED_ERR = "аварійно завершено (код {code})"
TXT_ALL_ON = "Запустити все"
TXT_ALL_OFF = "Закрити все"
TXT_BTN_ON = "Увімкнути"
TXT_BTN_OFF = "Вимкнути"
TXT_NO_KEYBOARD = (
    "Гарячі клавіші вимкнені: не встановлено бібліотеку keyboard "
    "(py -m pip install keyboard). Працюють лише кнопки у вікні."
)
TXT_ALREADY = "Панель керування вже запущена."


# ============================================================
# Параметри
# ============================================================

ROOT = Path(__file__).resolve().parent

CONFIG_FILE = ROOT / "control_panel.json"

IS_WIN = os.name == "nt"

OSC_HOST = "127.0.0.1"
OSC_PORT = 9000

# Порт-«замок», щоб не відкрити дві панелі (подвійні хоткеї).
LOCK_PORT = 47613

# Що відправити у VRChat після зупинки компонента.
OSC_RESET_GROUPS = {
    "move": (
        ("/input/MoveForward", False),
        ("/input/MoveBackward", False),
        ("/input/MoveLeft", False),
        ("/input/MoveRight", False),
        ("/input/Run", False),
    ),
    "look": (
        ("/input/LookHorizontal", 0.0),
        ("/input/LookVertical", 0.0),
    ),
    "hands": (
        ("/input/GrabRight", False),
        ("/input/UseRight", False),
    ),
}

DEFAULT_CONFIG = {
    "python": "auto",
    "autostart": ["phone", "camera", "launcher"],
    "all_hotkey": "f8",
    "close_vrchat_on_close_all": False,
    "components": [
        {
            "id": "phone",
            "title": "Телефон (SmartPhone)",
            "dir": "SmartPhone",
            "script": "main.py",
            "hotkey": "f5",
            "console": True,
            "osc_reset": ["move"],
        },
        {
            "id": "camera",
            "title": "Камера (MediaPipe)",
            "dir": "MediaPipe",
            "script": "main.py",
            "hotkey": "f6",
            "console": False,
            "osc_reset": ["look", "hands"],
        },
        {
            "id": "launcher",
            "title": "Лаунчер світів (VRChatApp)",
            "dir": "VRChatApp",
            "script": "main.py",
            "hotkey": "f7",
            "console": False,
            "osc_reset": [],
        },
    ],
}


# ============================================================
# Конфіг
# ============================================================

def load_config(path: Path = CONFIG_FILE) -> dict:
    """
    control_panel.json або значення за замовчуванням, якщо файлу немає.
    """

    if not path.exists():

        return json.loads(json.dumps(DEFAULT_CONFIG))

    with open(path, "r", encoding="utf-8") as f:

        config = json.load(f)

    for key, value in DEFAULT_CONFIG.items():

        config.setdefault(key, value)

    return config


def pick_python(setting: str = "auto", root: Path = ROOT) -> str:
    """
    Інтерпретатор для компонентів.

    "auto": .venv проєкту, якщо він є, інакше той самий python, що запустив
    панель (pythonw.exe підміняється на python.exe - потрібна консоль).
    """

    if setting and setting != "auto":

        return setting

    venv = root / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")

    if venv.exists():

        return str(venv)

    exe = Path(sys.executable)

    if IS_WIN and exe.name.lower() == "pythonw.exe":

        candidate = exe.with_name("python.exe")

        if candidate.exists():

            return str(candidate)

    return str(exe)


# ============================================================
# Завершення процесів
# ============================================================

def kill_tree(proc: subprocess.Popen, grace: float = 2.0):
    """
    Завершити процес разом з усіма дочірніми.
    """

    if proc.poll() is not None:

        return

    if IS_WIN:

        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )

    else:

        try:

            os.killpg(proc.pid, signal.SIGTERM)

        except ProcessLookupError:

            return

        try:

            proc.wait(timeout=grace)

            return

        except subprocess.TimeoutExpired:

            pass

        try:

            os.killpg(proc.pid, signal.SIGKILL)

        except ProcessLookupError:

            pass

    try:

        proc.wait(timeout=5)

    except subprocess.TimeoutExpired:

        pass


def kill_vrchat():
    """
    Закрити VRChat (лише Windows).
    """

    if not IS_WIN:

        return

    subprocess.run(
        ["taskkill", "/IM", "VRChat.exe", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x08000000,
    )


# ============================================================
# Компонент
# ============================================================

class Component:
    """
    Одна програма проєкту (окремий python-процес).
    """

    def __init__(self, spec: dict, python: str, root: Path = ROOT):

        self.id = spec["id"]
        self.title = spec.get("title", self.id)
        self.hotkey = spec.get("hotkey")
        self.console = bool(spec.get("console", False))
        self.osc_reset = list(spec.get("osc_reset", []))

        self.directory = root / spec["dir"]
        self.script = spec.get("script", "main.py")

        self.python = python
        self.log_dir = root / "logs"

        self.proc = None
        self._log = None

        # Чи оброблено вже аварійний вихід (щоб не слати OSC-скидання вдруге).
        self.exit_handled = True

    # --------------------------------------------------------

    def status(self):
        """
        ("running"|"stopped"|"exited", код виходу або None)
        """

        if self.proc is None:

            return "stopped", None

        code = self.proc.poll()

        if code is None:

            return "running", None

        return "exited", code

    def is_running(self) -> bool:

        return self.status()[0] == "running"

    # --------------------------------------------------------

    def start(self) -> bool:
        """
        Запустити компонент. False, якщо вже працює або запуск не вдався.
        """

        if self.is_running():

            return False

        self._close_log()

        if not (self.directory / self.script).exists():

            print(f"[{self.id}] не знайдено {self.directory / self.script}")

            return False

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        kwargs = {"cwd": str(self.directory), "env": env}

        if IS_WIN:

            kwargs["creationflags"] = (
                0x00000010 if self.console   # CREATE_NEW_CONSOLE
                else 0x08000000              # CREATE_NO_WINDOW
            )

        else:

            kwargs["start_new_session"] = True

        if not self.console:

            self.log_dir.mkdir(exist_ok=True)

            self._log = open(self.log_dir / f"{self.id}.log", "ab")

            stamp = time.strftime("%Y-%m-%d %H:%M:%S")

            self._log.write(f"\n===== {stamp} start =====\n".encode("utf-8"))
            self._log.flush()

            kwargs["stdout"] = self._log
            kwargs["stderr"] = subprocess.STDOUT
            kwargs["stdin"] = subprocess.DEVNULL

        try:

            self.proc = subprocess.Popen(
                [self.python, self.script],
                **kwargs
            )

        except OSError as e:

            print(f"[{self.id}] не вдалося запустити: {e}")

            self.proc = None

            self._close_log()

            return False

        self.exit_handled = False

        return True

    def stop(self) -> bool:
        """
        Зупинити компонент. False, якщо він і так не був запущений.
        """

        proc = self.proc

        if proc is None:

            return False

        was_running = proc.poll() is None

        kill_tree(proc)

        self.proc = None

        self.exit_handled = True

        self._close_log()

        return was_running

    def _close_log(self):

        if self._log is not None:

            try:

                self._log.close()

            except OSError:

                pass

            self._log = None


# ============================================================
# Контролер (без інтерфейсу)
# ============================================================

class Controller:
    """
    Керує набором компонентів. Не залежить від tkinter і клавіатури,
    тому його можна перевірити окремо.
    """

    def __init__(self, config: dict, root: Path = ROOT, osc_send=None):

        self.config = config

        python = pick_python(config.get("python", "auto"), root)

        self.components = [
            Component(spec, python, root)
            for spec in config["components"]
        ]

        self._osc_send = osc_send

        self._osc_client = None

    # --------------------------------------------------------

    def get(self, cid: str) -> Component:

        for component in self.components:

            if component.id == cid:

                return component

        raise KeyError(cid)

    def any_running(self) -> bool:

        return any(c.is_running() for c in self.components)

    # --------------------------------------------------------
    # OSC
    # --------------------------------------------------------

    def _send(self, address: str, value):

        if self._osc_send is not None:

            self._osc_send(address, value)

            return

        if self._osc_client is None:

            from pythonosc import udp_client

            self._osc_client = udp_client.SimpleUDPClient(OSC_HOST, OSC_PORT)

        self._osc_client.send_message(address, value)

    def reset_osc(self, groups):
        """
        Нейтральні OSC-значення для груп із OSC_RESET_GROUPS.

        Надсилається двічі: UDP не гарантує доставку, а залипла клавіша
        руху гірша за зайвий пакет.
        """

        messages = []

        for group in groups:

            messages.extend(OSC_RESET_GROUPS.get(group, ()))

        if not messages:

            return

        try:

            for _ in range(2):

                for address, value in messages:

                    self._send(address, value)

                time.sleep(0.03)

        except Exception as e:

            print(f"OSC-скидання не вдалося: {e}")

    # --------------------------------------------------------
    # Керування
    # --------------------------------------------------------

    def start(self, cid: str) -> bool:

        return self.get(cid).start()

    def stop(self, cid: str) -> bool:

        component = self.get(cid)

        stopped = component.stop()

        if stopped:

            self.reset_osc(component.osc_reset)

        return stopped

    def toggle(self, cid: str) -> str:
        """
        "started" або "stopped".
        """

        if self.get(cid).is_running():

            self.stop(cid)

            return "stopped"

        self.start(cid)

        return "started"

    def start_all(self):

        for component in self.components:

            component.start()

    def stop_all(self):

        groups = []

        for component in self.components:

            if component.stop():

                groups.extend(component.osc_reset)

        # Скидаємо й для тих, хто міг бути закритий вручну раніше.
        self.reset_osc(groups)

        if self.config.get("close_vrchat_on_close_all"):

            kill_vrchat()

    def toggle_all(self) -> str:
        """
        Щось працює - закрити все. Нічого не працює - запустити все.
        """

        if self.any_running():

            self.stop_all()

            return "stopped"

        self.start_all()

        return "started"

    def tick(self):
        """
        Викликати періодично: якщо компонент упав сам (код != 0), скинути
        його OSC-значення, щоб аватар не залип.
        """

        for component in self.components:

            state, code = component.status()

            if state == "exited" and not component.exit_handled:

                component.exit_handled = True

                if code != 0:

                    self.reset_osc(component.osc_reset)


# ============================================================
# Інтерфейс (tkinter + глобальні клавіші)
# ============================================================

def acquire_lock():
    """
    Сокет-замок: повертає сокет або None, якщо панель уже запущена.
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:

        sock.bind(("127.0.0.1", LOCK_PORT))

    except OSError:

        sock.close()

        return None

    return sock


def hotkey_label(key) -> str:

    return str(key).upper() if key else "-"


def run_ui(controller: Controller):

    import tkinter as tk

    config = controller.config

    root = tk.Tk()
    root.title(TITLE)
    root.resizable(False, False)
    root.attributes("-topmost", True)

    events = queue.Queue()

    # ---------------- Рядки компонентів ----------------

    rows = {}

    header = tk.Label(
        root,
        text="Гарячі клавіші працюють у будь-якому вікні",
        font=("Arial", 9),
        fg="#555555",
    )
    header.grid(row=0, column=0, columnspan=4, padx=12, pady=(10, 4))

    for index, component in enumerate(controller.components, start=1):

        key = tk.Label(
            root,
            text=f"[{hotkey_label(component.hotkey)}]",
            font=("Consolas", 12, "bold"),
            width=5,
        )
        key.grid(row=index, column=0, padx=(12, 4), pady=4)

        name = tk.Label(
            root,
            text=component.title,
            font=("Arial", 11),
            anchor="w",
            width=26,
        )
        name.grid(row=index, column=1, padx=4)

        state = tk.Label(
            root,
            text=TXT_STOPPED,
            font=("Arial", 10, "bold"),
            fg="#757575",
            width=30,
            anchor="w",
        )
        state.grid(row=index, column=2, padx=4)

        button = tk.Button(
            root,
            text=TXT_BTN_ON,
            width=11,
            command=lambda cid=component.id: events.put(
                lambda: controller.toggle(cid)
            ),
        )
        button.grid(row=index, column=3, padx=(4, 12), pady=4)

        rows[component.id] = (state, button)

    last = len(controller.components) + 1

    separator = tk.Frame(root, height=1, bg="#CCCCCC")
    separator.grid(
        row=last, column=0, columnspan=4,
        sticky="we", padx=12, pady=6
    )

    all_key = tk.Label(
        root,
        text=f"[{hotkey_label(config.get('all_hotkey'))}]",
        font=("Consolas", 12, "bold"),
        width=5,
    )
    all_key.grid(row=last + 1, column=0, padx=(12, 4), pady=4)

    all_name = tk.Label(
        root,
        text="Усі компоненти",
        font=("Arial", 11, "bold"),
        anchor="w",
    )
    all_name.grid(row=last + 1, column=1, padx=4, sticky="w")

    all_hint = tk.Label(
        root,
        text="щось працює - закрити все, інакше - запустити все",
        font=("Arial", 8),
        fg="#757575",
        anchor="w",
    )
    all_hint.grid(row=last + 1, column=2, padx=4, sticky="w")

    all_button = tk.Button(
        root,
        text=TXT_ALL_ON,
        width=13,
        command=lambda: events.put(controller.toggle_all),
    )
    all_button.grid(row=last + 1, column=3, padx=(4, 12), pady=4)

    notes = (
        "Окремо від панелі працюють клавіші самих програм:\n"
        "  телефон: F1 - калібрування, F2 - розумне калібрування, "
        "F9 - вихід\n"
        "  камера (вікно відео): 1 - калібрування, R - скидання, "
        "ESC - вихід\n"
        "  чутливість погляду: Shift +/- (гориз.), Ctrl +/- (верт.)"
    )

    notes_label = tk.Label(
        root,
        text=notes,
        font=("Consolas", 8),
        fg="#555555",
        justify="left",
        anchor="w",
    )
    notes_label.grid(
        row=last + 2, column=0, columnspan=4,
        sticky="w", padx=12, pady=(6, 4)
    )

    key_info = tk.Label(
        root,
        text="Остання клавіша, яку бачить панель: -",
        font=("Consolas", 8),
        fg="#1565C0",
        anchor="w",
    )
    key_info.grid(
        row=last + 3, column=0, columnspan=4,
        sticky="w", padx=12, pady=(0, 2)
    )

    warning = tk.Label(
        root,
        text="",
        font=("Arial", 8),
        fg="#B71C1C",
        wraplength=620,
        justify="left",
    )
    warning.grid(
        row=last + 4, column=0, columnspan=4,
        sticky="w", padx=12, pady=(0, 8)
    )

    # ---------------- Глобальні клавіші ----------------

    keyboard = None

    try:

        import keyboard as keyboard_module

        keyboard = keyboard_module

    except ImportError:

        warning.config(text=TXT_NO_KEYBOARD)

    last_key = {"name": "-"}

    if keyboard is not None:

        held = set()

        combo_last = {}

        def remember(event):

            if event.event_type == "down":

                last_key["name"] = event.name

        try:

            keyboard.hook(remember)

        except Exception as e:

            warning.config(text=f"Не вдалося увімкнути перехоплення: {e}")

        def bind(key, action):

            if not key:

                return

            key = str(key).lower().strip()

            try:

                if "+" in key:

                    # Комбінація (ctrl+f1): захист від повторів автоповтору.
                    def on_combo(key=key, action=action):

                        now = time.monotonic()

                        if now - combo_last.get(key, 0.0) < 0.6:

                            return

                        combo_last[key] = now

                        events.put(action)

                    keyboard.add_hotkey(key, on_combo)

                else:

                    # Одна клавіша: один натиск = одна дія, поки не відпустили.
                    def on_press(event, key=key, action=action):

                        if key in held:

                            return

                        held.add(key)

                        events.put(action)

                    def on_release(event, key=key):

                        held.discard(key)

                    keyboard.on_press_key(key, on_press)
                    keyboard.on_release_key(key, on_release)

            except Exception as e:

                warning.config(
                    text=f"Не вдалося призначити клавішу {key!r}: {e}"
                )

        for component in controller.components:

            bind(
                component.hotkey,
                lambda cid=component.id: controller.toggle(cid)
            )

        bind(config.get("all_hotkey"), controller.toggle_all)

    # ---------------- Оновлення ----------------

    def refresh():

        # 1. Команди з клавіатури/кнопок виконуються в потоці tkinter.
        try:

            while True:

                action = events.get_nowait()

                try:

                    action()

                except Exception as e:

                    warning.config(text=f"Помилка: {e}")

        except queue.Empty:

            pass

        key_info.config(
            text=f"Остання клавіша, яку бачить панель: {last_key['name']}"
        )

        # 2. Аварійне завершення компонентів.
        controller.tick()

        # 3. Індикатори.
        for component in controller.components:

            state, code = component.status()

            label, button = rows[component.id]

            if state == "running":

                label.config(text=TXT_RUNNING, fg="#2E7D32")
                button.config(text=TXT_BTN_OFF)

            elif state == "exited":

                if code == 0:

                    label.config(text=TXT_EXITED_OK, fg="#757575")

                else:

                    text = TXT_EXITED_ERR.format(code=code)

                    if not component.console:

                        text += f" - logs/{component.id}.log"

                    label.config(text=text, fg="#B71C1C")

                button.config(text=TXT_BTN_ON)

            else:

                label.config(text=TXT_STOPPED, fg="#757575")
                button.config(text=TXT_BTN_ON)

        all_button.config(
            text=TXT_ALL_OFF if controller.any_running() else TXT_ALL_ON
        )

        root.after(300, refresh)

    def on_close():

        if keyboard is not None:

            try:

                keyboard.unhook_all()

            except Exception:

                pass

        controller.stop_all()

        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # ---------------- Автозапуск ----------------

    for cid in config.get("autostart", []):

        try:

            controller.start(cid)

        except KeyError:

            warning.config(text=f"autostart: невідомий компонент {cid!r}")

    root.after(300, refresh)

    try:

        root.mainloop()

    finally:

        # Панель не повинна залишати після себе «осиротілі» процеси.
        controller.stop_all()


# ============================================================
# Main
# ============================================================

def main():

    lock = acquire_lock()

    if lock is None:

        print(TXT_ALREADY)

        try:

            import tkinter as tk
            from tkinter import messagebox

            hidden = tk.Tk()
            hidden.withdraw()
            messagebox.showinfo(TITLE, TXT_ALREADY)
            hidden.destroy()

        except Exception:

            pass

        return

    try:

        controller = Controller(load_config())

        run_ui(controller)

    except Exception:

        # Під pythonw консолі немає, тож пишемо помилку у файл.
        log_dir = ROOT / "logs"

        log_dir.mkdir(exist_ok=True)

        with open(log_dir / "control_panel.log", "a", encoding="utf-8") as f:

            f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            f.write(traceback.format_exc())

        raise

    finally:

        lock.close()


if __name__ == "__main__":

    main()
