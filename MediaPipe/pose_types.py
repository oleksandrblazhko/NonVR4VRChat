"""
pose_types.py

Базові типи даних для системи трекінгу.

Автор: OpenAI
"""

from __future__ import annotations

from dataclasses import dataclass, field

from math3d import Vector3


# ============================================================
# Joint
# ============================================================

@dataclass(slots=True)
class Joint:
    """
    Один суглоб.
    """

    position: Vector3 = field(default_factory=Vector3)

    visibility: float = 1.0


# ============================================================
# Skeleton
# ============================================================

@dataclass(slots=True)
class Skeleton:
    """
    Мінімальний набір точок MediaPipe,
    необхідний для керування LookHorizontal
    та LookVertical.
    """

    nose: Joint = field(default_factory=Joint)

    left_shoulder: Joint = field(default_factory=Joint)
    right_shoulder: Joint = field(default_factory=Joint)

    left_hip: Joint = field(default_factory=Joint)
    right_hip: Joint = field(default_factory=Joint)

    # --------------------------------------------------------

    def shoulder_center(self) -> Vector3:
        """
        Центр плечей.
        """

        return (
            self.left_shoulder.position +
            self.right_shoulder.position
        ) / 2.0

    # --------------------------------------------------------

    def hip_center(self) -> Vector3:
        """
        Центр стегон.
        """

        return (
            self.left_hip.position +
            self.right_hip.position
        ) / 2.0

    # --------------------------------------------------------

    def shoulder_vector(self) -> Vector3:
        """
        Вектор від лівого плеча
        до правого.
        """

        return (
            self.right_shoulder.position -
            self.left_shoulder.position
        )

    # --------------------------------------------------------

    def torso_vector(self) -> Vector3:
        """
        Вектор від центру стегон
        до центру плечей.
        """

        return (
            self.shoulder_center() -
            self.hip_center()
        )

    # --------------------------------------------------------

    def head_vector(self) -> Vector3:
        """
        Вектор від центру плечей
        до носа.
        """

        return (
            self.nose.position -
            self.shoulder_center()
        )


# ============================================================
# PoseFrame
# ============================================================

@dataclass(slots=True)
class PoseFrame:
    """
    Один кадр трекінгу.
    """

    frame_number: int = 0

    timestamp: float = 0.0

    fps: float = 0.0

    skeleton: Skeleton = field(default_factory=Skeleton)

    