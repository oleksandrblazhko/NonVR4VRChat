"""
look_controller.py

Перетворення метрик повороту та нахилу
у команди VRChat:

    LookHorizontal
    LookVertical

Алгоритм:
1. Отримує метрики.
2. Віднімає нейтральні метрики.
3. Масштабує значення.
4. Застосовує Dead Zone.
5. Масштабує у діапазон VRChat.
6. Застосовує EMA.
"""

from __future__ import annotations

import os
import json
import math


# ============================================================
# Parameters
# ============================================================

HORIZONTAL_CENTER = 0.5
VERTICAL_CENTER = 0.1
MAX_SENSITIVITY_MULTIPLIER = 10.0 # 100% sensitivity will equal this multiplier

# ============================================================
# LookController
# ============================================================

class LookController:

    def __init__(self):

        self.horizontal = HORIZONTAL_CENTER
        self.vertical = VERTICAL_CENTER

        # Налаштування за замовчуванням
        self.max_horizontal_metric = 0.2
        self.horizontal_threshold_metric = 0.02
        self.horizontal_sensitivity_pct = 30.0

        self.max_vertical_metric = 0.1
        self.vertical_threshold_metric = 0.01
        self.vertical_sensitivity_pct = 30.0
        
        self.smooth = 0.25

        # Завантаження конфігурації з control.json
        try:
            config_path = os.path.join(os.path.dirname(__file__), "control.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    
                    var_settings = config.get("var_settings", {})
                    # Горизонтальні налаштування
                    self.max_horizontal_metric = float(var_settings.get("max_horizontal_metric", 0.2))
                    self.horizontal_threshold_metric = float(var_settings.get("horizontal_threshold_metric", 0.02))
                    self.horizontal_sensitivity_pct = float(var_settings.get("horizontal_sensitivity_pct", 30.0))

                    # Вертикальні налаштування
                    self.max_vertical_metric = float(var_settings.get("max_vertical_metric", 0.1))
                    self.vertical_threshold_metric = float(var_settings.get("vertical_threshold_metric", 0.01))
                    self.vertical_sensitivity_pct = float(var_settings.get("vertical_sensitivity_pct", 30.0))
                    
                    self.smooth = float(var_settings.get("smooth", 0.25))

                print("Loaded control.json for full metric-based algorithm.")
                print(
                    f"  horizontal settings: max_metric={self.max_horizontal_metric}, "
                    f"threshold={self.horizontal_threshold_metric}, sensitivity={self.horizontal_sensitivity_pct}%"
                )
                print(
                    f"  vertical settings: max_metric={self.max_vertical_metric}, "
                    f"threshold={self.vertical_threshold_metric}, sensitivity={self.vertical_sensitivity_pct}%"
                )

            else:
                print("control.json not found, using default settings for full metric-based algorithm.")
        except Exception as e:
            print(f"Error loading control.json: {e}. Using default settings.")

    def reset(self):
        self.horizontal = HORIZONTAL_CENTER
        self.vertical = VERTICAL_CENTER

    @staticmethod
    def clamp(value, minimum, maximum):
        return max(minimum, min(maximum, value))

    @staticmethod
    def normalize_metric(
        metric_val: float,
        dead_zone: float,
        max_metric: float
    ) -> float:
        """
        Перетворення метрики у [-1 ; +1] з квадратичною характеристикою.
        """
        if abs(metric_val) <= dead_zone:
            return 0.0

        if metric_val > 0.0:
            val = metric_val - dead_zone
        else:
            val = metric_val + dead_zone
        
        span = max_metric - dead_zone
        if span <= 0:
            return 0.0

        value = val / span
        value = LookController.clamp(value, -1.0, 1.0)
        sign = 1.0 if value >= 0.0 else -1.0
        value = value * value
        return sign * value

    def update(
            self,
            yaw_metric: float,
            pitch_metric: float,
            neutral_yaw_metric: float,
            neutral_pitch_metric: float
    ) -> tuple[float, float]:
        """
        Перетворення метрик повороту та нахилу у команди VRChat.
        """
        # ----------------------------------------------------
        # Горизонтальний розрахунок
        # ----------------------------------------------------
        
        yaw_offset = yaw_metric - neutral_yaw_metric
        horizontal_multiplier = (self.horizontal_sensitivity_pct / 100.0) * MAX_SENSITIVITY_MULTIPLIER
        scaled_yaw = yaw_offset * horizontal_multiplier
        yaw = self.normalize_metric(
            scaled_yaw,
            self.horizontal_threshold_metric,
            self.max_horizontal_metric
        )

        if yaw == 0.0:
            target_horizontal = HORIZONTAL_CENTER
        elif yaw > 0.0:
            target_horizontal = HORIZONTAL_CENTER + 0.5 * yaw
        else:
            target_horizontal = -HORIZONTAL_CENTER + 0.5 * yaw
            
        # ----------------------------------------------------
        # Вертикальний розрахунок
        # ----------------------------------------------------
        pitch_offset = pitch_metric - neutral_pitch_metric
        vertical_multiplier = (self.vertical_sensitivity_pct / 100.0) * MAX_SENSITIVITY_MULTIPLIER
        scaled_pitch = pitch_offset * vertical_multiplier
        pitch = self.normalize_metric(
            scaled_pitch,
            self.vertical_threshold_metric,
            self.max_vertical_metric
        )
        
        if pitch == 0.0:
            target_vertical = VERTICAL_CENTER
        elif pitch > 0.0:
            target_vertical = VERTICAL_CENTER + 0.9 * pitch
        else:
            target_vertical = -VERTICAL_CENTER + 0.9 * pitch

        # ----------------------------------------------------
        # Clamp & EMA (Спільне для обох)
        # ----------------------------------------------------
        target_horizontal = self.clamp(target_horizontal, -1.0, 1.0)
        target_vertical = self.clamp(target_vertical, -1.0, 1.0)

        self.horizontal += (target_horizontal - self.horizontal) * (1.0 - self.smooth)
        self.vertical += (target_vertical - self.vertical) * (1.0 - self.smooth)

        return (self.horizontal, self.vertical)
    