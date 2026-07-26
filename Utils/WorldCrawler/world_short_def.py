#!/usr/bin/env python3
"""
Об'єднання скорочених описів VRChat-світів.

Використання:
    python world_short_def.py <каталог>

Результат:
    world_short_def.json
"""

import json
import sys
from pathlib import Path

OUTPUT_FILE = Path("world_short_def.json")


def process_world(world):
    """Повернути скорочений опис світу."""
    return {
        "id": world.get("id"),
        "name": world.get("name"),
        "popularity": world.get("popularity"),
        "tags": world.get("tags", [])
    }


def load_existing():
    """Завантажити вже накопичені світи."""
    worlds = {}

    if not OUTPUT_FILE.exists():
        return worlds

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            for world in data:
                if isinstance(world, dict) and "id" in world:
                    worlds[world["id"]] = world

    except Exception as e:
        print(f"Попередній файл не вдалося прочитати: {e}")

    return worlds


def main():

    if len(sys.argv) != 2:
        print("Використання:")
        print("    python world_short_def.py <каталог>")
        sys.exit(1)

    folder = Path(sys.argv[1])

    if not folder.is_dir():
        print(f"Каталог не знайдено: {folder}")
        sys.exit(1)

    # Завантажуємо вже накопичені результати
    worlds = load_existing()

    existing_count = len(worlds)

    files_processed = 0
    worlds_read = 0
    new_worlds = 0
    updated_worlds = 0

    for json_file in sorted(folder.glob("*.json")):

        files_processed += 1

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                iterable = data
            elif isinstance(data, dict):
                iterable = [data]
            else:
                continue

            for world in iterable:

                if not isinstance(world, dict):
                    continue

                world_id = world.get("id")

                if not world_id:
                    continue

                worlds_read += 1

                if world_id in worlds:
                    updated_worlds += 1
                else:
                    new_worlds += 1

                worlds[world_id] = process_world(world)

        except Exception as e:
            print(f"Помилка читання {json_file.name}: {e}")

    output = sorted(worlds.values(), key=lambda x: x["name"].lower())

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print()
    print("========== Статистика ==========")
    print(f"Опрацьовано файлів      : {files_processed}")
    print(f"Прочитано описів світів : {worlds_read}")
    print(f"Було у файлі            : {existing_count}")
    print(f"Нових світів            : {new_worlds}")
    print(f"Оновлено дублікатів     : {updated_worlds}")
    print(f"Всього унікальних світів: {len(worlds)}")
    print(f"Результат записано у    : {OUTPUT_FILE}")
    print("================================")


if __name__ == "__main__":
    
    main()