import json
from pathlib import Path


CONFIG_FILE = Path(__file__).resolve().parent / "config.json"


def load_config(filename=None):
    if filename is None:
        filename = CONFIG_FILE

    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)
    