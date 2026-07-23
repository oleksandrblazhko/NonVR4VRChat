"""
filters.py

Фільтри для згладжування сигналів.

Автор: OpenAI
"""

from __future__ import annotations


# ============================================================
# EMAFilter
# ============================================================

class EMAFilter:
    """
    Exponential Moving Average.
    """

    def __init__(
            self,
            alpha: float = 0.25
    ):

        self.alpha = alpha

        self.value = 0.0

        self.initialized = False

    # --------------------------------------------------------

    def reset(self):

        self.value = 0.0

        self.initialized = False

    # --------------------------------------------------------

    def update(
            self,
            x: float
    ) -> float:

        if not self.initialized:

            self.value = x

            self.initialized = True

            return x

        self.value = (

            self.alpha * x +

            (1.0 - self.alpha) * self.value

        )

        return self.value


# ============================================================
# DeadZoneFilter
# ============================================================

class DeadZoneFilter:
    """
    Мертва зона.
    """

    def __init__(
            self,
            threshold: float = 0.05
    ):

        self.threshold = threshold

    # --------------------------------------------------------

    def update(
            self,
            x: float
    ) -> float:

        if abs(x) < self.threshold:

            return 0.0

        return x


# ============================================================
# LookFilter
# ============================================================

class LookFilter:
    """
    Комплексний фільтр
    для yaw та pitch.
    """

    def __init__(self):

        self.yaw_filter = EMAFilter()

        self.pitch_filter = EMAFilter()

        self.dead_zone = DeadZoneFilter()

    # --------------------------------------------------------

    def reset(self):

        self.yaw_filter.reset()

        self.pitch_filter.reset()

    # --------------------------------------------------------

    def update(
            self,
            yaw: float,
            pitch: float
    ):

        yaw = self.dead_zone.update(yaw)

        pitch = self.dead_zone.update(pitch)

        yaw = self.yaw_filter.update(yaw)

        pitch = self.pitch_filter.update(pitch)

        return yaw, pitch
    
    