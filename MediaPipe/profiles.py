"""
profiles.py

Профілі користувачів: іменовані набори параметрів керування поглядом.

Профілі зберігаються у `config.json` у списку `profiles`. Кожен профіль -
це об'єкт з назвою (`name`) та параметрами, які раніше лежали в секції
`var_settings`:

    {
      "active_profile": "Default",
      "profiles": [
        {
          "name": "Default",
          "horizontal_sensitivity_pct": 16.0,
          ...
        }
      ]
    }

`active_profile` - назва профілю, який вибрано на старті. Якщо файл
старого формату (є лише `var_settings`), він читається як єдиний профіль
`Default`, а при першому збереженні переписується у новий формат.
"""

from __future__ import annotations

import json
import os


# ============================================================
# Parameters
# ============================================================

CONFIG_FILE = "config.json"

DEFAULT_PROFILE_NAME = "Default"

# Параметри профілю та їхні значення за замовчуванням
# (ті самі, що раніше були у LookController).
PROFILE_DEFAULTS = {
    "horizontal_sensitivity_pct": 30.0,
    "max_horizontal_metric": 0.2,
    "horizontal_threshold_metric": 0.02,
    "vertical_sensitivity_pct": 30.0,
    "max_vertical_metric": 0.1,
    "vertical_threshold_metric": 0.01,
    "smooth": 0.25,
}


# ============================================================
# Helpers
# ============================================================

def _normalize_profile(raw, fallback_name: str) -> dict:
    """
    Привести сирий профіль із файлу до повного вигляду: назва плюс усі
    параметри. Відсутні або некоректні значення беруться за замовчуванням.
    """

    raw = raw if isinstance(raw, dict) else {}

    name = str(raw.get("name") or fallback_name).strip() or fallback_name

    profile = {"name": name}

    for key, default in PROFILE_DEFAULTS.items():

        try:

            profile[key] = float(raw.get(key, default))

        except (TypeError, ValueError):

            profile[key] = default

    return profile


# ============================================================
# ProfileManager
# ============================================================

class ProfileManager:
    """
    Читає профілі з `config.json`, тримає активний і записує зміни назад.
    """

    def __init__(self, path: str | None = None):

        self.path = path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            CONFIG_FILE
        )

        self.profiles: list[dict] = []

        self.active_index = 0

        self.load()

    # --------------------------------------------------------
    # Load / save
    # --------------------------------------------------------

    def load(self) -> None:
        """
        Прочитати профілі. Немає файлу, битий JSON або немає профілів -
        лишається один профіль `Default` зі значеннями за замовчуванням.
        """

        config = {}

        try:

            with open(self.path, "r", encoding="utf-8") as f:

                loaded = json.load(f)

            if isinstance(loaded, dict):

                config = loaded

        except FileNotFoundError:

            print(f"{CONFIG_FILE} not found, using default profile.")

        except Exception as e:

            print(f"Error loading {CONFIG_FILE}: {e}. Using default profile.")

        profiles = []

        raw_profiles = config.get("profiles")

        if isinstance(raw_profiles, list):

            for i, raw in enumerate(raw_profiles):

                profile = _normalize_profile(raw, f"Profile {i + 1}")

                # Назви мають бути унікальними: за ними профіль вибирають.
                if any(p["name"] == profile["name"] for p in profiles):

                    continue

                profiles.append(profile)

        if not profiles:

            # Старий формат: параметри лежать у var_settings.
            profiles.append(
                _normalize_profile(
                    config.get("var_settings"),
                    DEFAULT_PROFILE_NAME
                )
            )

            profiles[0]["name"] = DEFAULT_PROFILE_NAME

        self.profiles = profiles

        active_name = config.get("active_profile")

        self.active_index = 0

        for i, profile in enumerate(self.profiles):

            if profile["name"] == active_name:

                self.active_index = i

                break

    # --------------------------------------------------------

    def save(self) -> bool:
        """
        Записати профілі та `active_profile` у `config.json`.

        Решта ключів файлу зберігається. Застарілу секцію `var_settings`
        прибрано: її параметри тепер живуть у профілях.
        """

        try:

            with open(self.path, "r", encoding="utf-8") as f:

                config = json.load(f)

            if not isinstance(config, dict):

                config = {}

        except FileNotFoundError:

            config = {}

        except Exception as e:

            # Не перетираємо файл, який не вдалося прочитати.
            print(f"Не вдалось зберегти {CONFIG_FILE}: {e}")

            return False

        config.pop("var_settings", None)

        config["active_profile"] = self.active_name

        config["profiles"] = [dict(p) for p in self.profiles]

        try:

            with open(self.path, "w", encoding="utf-8") as f:

                json.dump(config, f, indent=2, ensure_ascii=False)

                f.write("\n")

        except Exception as e:

            print(f"Не вдалось зберегти {CONFIG_FILE}: {e}")

            return False

        return True

    # --------------------------------------------------------
    # Access
    # --------------------------------------------------------

    @property
    def names(self) -> list[str]:

        return [p["name"] for p in self.profiles]

    @property
    def active_name(self) -> str:

        return self.profiles[self.active_index]["name"]

    @property
    def active_settings(self) -> dict:
        """
        Параметри активного профілю (без назви) - копія.
        """

        profile = self.profiles[self.active_index]

        return {key: profile[key] for key in PROFILE_DEFAULTS}

    # --------------------------------------------------------
    # Switching
    # --------------------------------------------------------

    def switch(self, step: int = 1) -> str:
        """
        Перейти на наступний (`step` = +1) або попередній (`step` = -1)
        профіль по колу. Повертає назву нового активного профілю.
        """

        self.active_index = (self.active_index + step) % len(self.profiles)

        return self.active_name

    # --------------------------------------------------------

    def select(self, name: str) -> bool:
        """
        Зробити активним профіль за назвою. False, якщо такого немає.
        """

        for i, profile in enumerate(self.profiles):

            if profile["name"] == name:

                self.active_index = i

                return True

        return False

    # --------------------------------------------------------

    def update_active(self, values: dict) -> None:
        """
        Оновити параметри активного профілю у пам'яті (файл не чіпає).
        Невідомі ключі ігноруються.
        """

        profile = self.profiles[self.active_index]

        for key, value in values.items():

            if key in PROFILE_DEFAULTS:

                profile[key] = float(value)
