"""
body_tracker.py

Обчислення геометрії тулуба.

BodyTracker НЕ залежить від VRChat і НЕ виконує
перетворення кутів у OSC-команди.

Модуль визначає:

- центр плечей;
- напрямок плечей;
- напрямок тулуба;
- метрику повороту yaw;
- метрику нахилу pitch.

Подальше перетворення цих значень у команди
VRChat виконує модуль look_controller.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import math

from math3d import (
    Vector3,
    normalize
)

from pose_types import PoseFrame
from calibration import Calibration


# ============================================================
# BodyState
# ============================================================

@dataclass(slots=True)
class BodyState:
    """
    Поточний стан тулуба.
    """

    shoulder_center: Vector3 = Vector3()

    shoulder_vector: Vector3 = Vector3()

    torso_vector: Vector3 = Vector3()

    #
    # Метрики повороту та нахилу.
    #

    yaw_metric: float = 0.0

    pitch_metric: float = 0.0


# ============================================================
# BodyTracker
# ============================================================

class BodyTracker:

    def __init__(
            self,
            calibration: Calibration
    ):

        self.calibration = calibration

    # --------------------------------------------------------

    def update(
            self,
            frame: PoseFrame
    ) -> BodyState:
        """
        Аналіз поточного кадру.
        """

        skeleton = frame.skeleton

        shoulder_center = (
            skeleton.shoulder_center()
        )

        shoulder_vector = normalize(

            skeleton.shoulder_vector()

        )

        torso_vector = normalize(

            skeleton.head_vector()

        )

        state = BodyState(

            shoulder_center=shoulder_center,

            shoulder_vector=shoulder_vector,

            torso_vector=torso_vector

        )

        #
        # Метрики повороту та нахилу.
        #

        ear_center_x = (skeleton.left_ear.position.x + skeleton.right_ear.position.x) / 2.0
        ear_center_y = (skeleton.left_ear.position.y + skeleton.right_ear.position.y) / 2.0

        ear_dist = max(abs(skeleton.left_ear.position.x - skeleton.right_ear.position.x), 0.02)
        # Нова z-less метрика для yaw
        state.yaw_metric = ((ear_center_x - skeleton.nose.position.x) / ear_dist)
        
        # Нова z-less метрика для pitch
        state.pitch_metric = ((ear_center_y - skeleton.nose.position.y) / ear_dist)

        return state

    # --------------------------------------------------------

    def print(
            self,
            state: BodyState
    ):

        print("--------------------------------")

        print(

            f"Yaw metric   : "
            f"{state.yaw_metric:7.2f}"

        )

        print(

            f"Pitch metric : "
            f"{state.pitch_metric:7.2f}"

        )

        print()

        print("Shoulder vector")

        print(

            state.shoulder_vector

        )

        print()

        print("Torso vector")

        print(

            state.torso_vector

        )

        print("--------------------------------")

        