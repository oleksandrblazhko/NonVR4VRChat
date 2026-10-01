import json


def load_config(filename="config.json"):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)
    
    