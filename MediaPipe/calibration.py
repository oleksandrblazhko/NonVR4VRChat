"""
calibration.py

Зберігання нейтрального положення користувача.

Автор: OpenAI
"""

from __future__ import annotations


class Calibration:
    """
    Нейтральні метрики користувача.
    """

    def __init__(self):

        self.reset()

    # --------------------------------------------------------

    def reset(self):
        """
        Скидання калібрування.
        """

        self.ready = False

        self.neutral_yaw_metric = 0.0

        self.neutral_pitch_metric = 0.0

    # --------------------------------------------------------

    def set_neutral(
            self,
            yaw_metric: float,
            pitch_metric: float
    ):
        """
        Зберегти нейтральні значення.
        """

        self.neutral_yaw_metric = yaw_metric

        self.neutral_pitch_metric = pitch_metric

        self.ready = True

    # --------------------------------------------------------

    def is_ready(self):
        """
        Перевірка готовності.
        """

        return self.ready

    # --------------------------------------------------------

    def print(self):
        """
        Виведення параметрів калібрування.
        """

        if not self.ready:

            print("Calibration not completed.")

            return

        print("--------------------------------")

        print("Calibration")

        print()

        print(
            f"Neutral yaw metric   : "
            f"{self.neutral_yaw_metric:.3f}"
        )

        print(
            f"Neutral pitch metric : "
            f"{self.neutral_pitch_metric:.3f}"
        )

        print("--------------------------------")


        