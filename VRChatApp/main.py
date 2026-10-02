from tkinter import Tk

from config import load_config
from gui import VRChatLauncher


def main():
    config = load_config()

    root = Tk()

    VRChatLauncher(root, config)

    root.mainloop()


if __name__ == "__main__":
    main()
