import tkinter as tk


class CommandGUI:
    def __init__(self):
        self.root = tk.Tk()

        self.root.title("VRChat Smartphone Control")
        self.root.geometry("500x500")
        self.root.resizable(False, False)

        self.buttons = {}

        self._create_gui()

    def _create_gui(self):
        frame = tk.Frame(self.root)

        frame.pack(
            expand=True
        )

        self.buttons["/input/MoveForward"] = (
            self._create_button(
                frame,
                "↑\nВПЕРЕД",
                row=0,
                column=1
            )
        )

        self.buttons["/input/MoveLeft"] = (
            self._create_button(
                frame,
                "←\nВЛІВО",
                row=1,
                column=0
            )
        )

        self.buttons["/input/MoveRight"] = (
            self._create_button(
                frame,
                "→\nВПРАВО",
                row=1,
                column=2
            )
        )

        self.buttons["/input/MoveBackward"] = (
            self._create_button(
                frame,
                "↓\nНАЗАД",
                row=2,
                column=1
            )
        )

    def _create_button(
        self,
        parent,
        text,
        row,
        column
    ):
        button = tk.Label(
            parent,
            text=text,
            width=12,
            height=5,
            font=("Arial", 16, "bold"),
            relief="raised",
            bd=3
        )

        button.grid(
            row=row,
            column=column,
            padx=10,
            pady=10
        )

        return button

    def update_command(
        self,
        command,
        active
    ):
        """
        Оновлює стан команди.

        Цей метод може викликатися
        з іншого потоку.
        """

        self.root.after(
            0,
            self._update_command,
            command,
            active
        )

    def _update_command(
        self,
        command,
        active
    ):
        if command not in self.buttons:
            return

        button = self.buttons[command]

        if active:

            button.config(
                relief="sunken",
                bd=5
            )

        else:

            button.config(
                relief="raised",
                bd=3
            )

    def run(self):
        """
        Запускає головний цикл Tkinter.
        """

        self.root.mainloop()
        