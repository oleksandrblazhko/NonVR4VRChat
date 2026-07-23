"""
math3d.py

Прості математичні функції для роботи з тривимірними векторами.

Використовується модулями:
    - pose_types.py
    - calibration.py
    - body_tracker.py

Автор: OpenAI
"""

from __future__ import annotations

from dataclasses import dataclass
import math


# ============================================================
# Vector3
# ============================================================

@dataclass(slots=True)
class Vector3:
    """
    Тривимірний вектор.
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # --------------------------------------------------------

    def __add__(self, other: "Vector3") -> "Vector3":
        return Vector3(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z
        )

    # --------------------------------------------------------

    def __sub__(self, other: "Vector3") -> "Vector3":
        return Vector3(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z
        )

    # --------------------------------------------------------

    def __mul__(self, value: float) -> "Vector3":
        return Vector3(
            self.x * value,
            self.y * value,
            self.z * value
        )

    # --------------------------------------------------------

    def __rmul__(self, value: float) -> "Vector3":
        return self.__mul__(value)

    # --------------------------------------------------------

    def __truediv__(self, value: float) -> "Vector3":

        if value == 0:
            raise ZeroDivisionError("Division by zero.")

        return Vector3(
            self.x / value,
            self.y / value,
            self.z / value
        )

    # --------------------------------------------------------

    def length(self) -> float:
        """
        Довжина вектора.
        """
        return math.sqrt(
            self.x * self.x +
            self.y * self.y +
            self.z * self.z
        )

    # --------------------------------------------------------

    def normalized(self) -> "Vector3":
        """
        Нормалізований вектор.
        """

        l = self.length()

        if l < 1e-9:
            return Vector3()

        return self / l

    # --------------------------------------------------------

    def tuple(self):
        return (
            self.x,
            self.y,
            self.z
        )

    # --------------------------------------------------------

    def copy(self):
        return Vector3(
            self.x,
            self.y,
            self.z
        )

    # --------------------------------------------------------

    def __repr__(self):
        return (
            f"Vector3("
            f"{self.x:.4f}, "
            f"{self.y:.4f}, "
            f"{self.z:.4f})"
        )


# ============================================================
# Vector functions
# ============================================================

def length(v: Vector3) -> float:
    """
    Довжина вектора.
    """
    return v.length()


# ------------------------------------------------------------

def normalize(v: Vector3) -> Vector3:
    """
    Нормалізація.
    """
    return v.normalized()


# ------------------------------------------------------------

def dot(a: Vector3, b: Vector3) -> float:
    """
    Скалярний добуток.
    """
    return (
        a.x * b.x +
        a.y * b.y +
        a.z * b.z
    )


# ------------------------------------------------------------

def cross(a: Vector3, b: Vector3) -> Vector3:
    """
    Векторний добуток.
    """

    return Vector3(

        a.y * b.z - a.z * b.y,

        a.z * b.x - a.x * b.z,

        a.x * b.y - a.y * b.x

    )


# ------------------------------------------------------------

def distance(a: Vector3, b: Vector3) -> float:
    """
    Відстань між двома точками.
    """
    return (a - b).length()


# ------------------------------------------------------------

def midpoint(a: Vector3, b: Vector3) -> Vector3:
    """
    Середина відрізка.
    """
    return (a + b) / 2.0


# ------------------------------------------------------------

def clamp(
        value: float,
        minimum: float,
        maximum: float
) -> float:
    """
    Обмеження значення.
    """

    return max(
        minimum,
        min(maximum, value)
    )


# ------------------------------------------------------------

def angle(
        a: Vector3,
        b: Vector3
) -> float:
    """
    Кут між векторами у градусах.
    """

    aa = normalize(a)
    bb = normalize(b)

    value = dot(aa, bb)

    value = clamp(
        value,
        -1.0,
        1.0
    )

    return math.degrees(
        math.acos(value)
    )


# ------------------------------------------------------------

def lerp(
        a: Vector3,
        b: Vector3,
        t: float
) -> Vector3:
    """
    Лінійна інтерполяція.
    """

    t = clamp(
        t,
        0.0,
        1.0
    )

    return a * (1.0 - t) + b * t


# ------------------------------------------------------------

def project(
        a: Vector3,
        b: Vector3
) -> Vector3:
    """
    Проєкція вектора a на вектор b.
    """

    bb = dot(b, b)

    if bb < 1e-9:
        return Vector3()

    return b * (dot(a, b) / bb)


# ------------------------------------------------------------

def deg2rad(angle: float) -> float:
    return math.radians(angle)


# ------------------------------------------------------------

def rad2deg(angle: float) -> float:
    return math.degrees(angle)
