"""
mediapipe_adapter.py

Перетворення результатів MediaPipe Pose
у внутрішні структури проекту.

Автор: OpenAI
"""

from __future__ import annotations

import time

from math3d import Vector3
from pose_types import (
    Joint,
    Skeleton,
    PoseFrame
)

# ============================================================
# MediaPipe Pose Landmark Index
# ============================================================

NOSE = 0

LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12

LEFT_HIP = 23
RIGHT_HIP = 24


# ============================================================
# Лічильник кадрів
# ============================================================

_frame_counter = 0


# ============================================================
# Допоміжні функції
# ============================================================

def create_joint(landmark) -> Joint:
    """
    Створює Joint із MediaPipe Landmark.
    """

    return Joint(

        position=Vector3(

            landmark.x,

            landmark.y,

            landmark.z

        ),

        visibility=getattr(
            landmark,
            "visibility",
            1.0
        )

    )


# ============================================================
# Основна функція
# ============================================================

def create_pose_frame(
        pose_landmarks,
        fps: float = 0.0
) -> PoseFrame:
    """
    Перетворення MediaPipe Pose
    у PoseFrame.

    Parameters
    ----------
    pose_landmarks :
        results.pose_landmarks

    fps :
        Поточний FPS.

    Returns
    -------
    PoseFrame
    """

    global _frame_counter

    _frame_counter += 1

    lm = pose_landmarks.landmark

    skeleton = Skeleton(

        nose=create_joint(
            lm[NOSE]
        ),

        left_shoulder=create_joint(
            lm[LEFT_SHOULDER]
        ),

        right_shoulder=create_joint(
            lm[RIGHT_SHOULDER]
        ),

        left_hip=create_joint(
            lm[LEFT_HIP]
        ),

        right_hip=create_joint(
            lm[RIGHT_HIP]
        )

    )

    return PoseFrame(

        frame_number=_frame_counter,

        timestamp=time.time(),

        fps=fps,

        skeleton=skeleton

    )


# ============================================================
# Перевірка
# ============================================================

def print_pose_frame(
        frame: PoseFrame
):
    """
    Виведення інформації про кадр.
    """

    print("----------------------------------------")

    print(f"Frame : {frame.frame_number}")

    print(f"FPS   : {frame.fps:.1f}")

    print(f"Time  : {frame.timestamp:.3f}")

    print()

    print("Nose")

    print(frame.skeleton.nose.position)

    print()

    print("Left shoulder")

    print(frame.skeleton.left_shoulder.position)

    print()

    print("Right shoulder")

    print(frame.skeleton.right_shoulder.position)

    print()

    print("Left hip")

    print(frame.skeleton.left_hip.position)

    print()

    print("Right hip")

    print(frame.skeleton.right_hip.position)

    print()

    print("Shoulder center")

    print(frame.skeleton.shoulder_center())

    print()

    print("Hip center")

    print(frame.skeleton.hip_center())

    print("----------------------------------------")

    