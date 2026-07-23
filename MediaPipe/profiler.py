"""
profiler.py

Збереження часових міток для аналізу затримок.
"""

import time


class StepProfiler:
    """
    Зберігає часові мітки проходження одного кадру.
    """

    STEP_COUNT = 8

    STEP_CAPTURE = 0
    STEP_MEDIAPIPE = 1
    STEP_ADAPTER = 2
    STEP_TRACKER = 3
    STEP_CALIBRATION = 4
    STEP_CONTROLLER = 5
    STEP_OSC = 6
    STEP_FRAME_END = 7

    def __init__(self):
        self.timestamps = [0] * self.STEP_COUNT

    def mark(self, step: int):
        """
        Зберегти поточний момент часу.
        """
        self.timestamps[step] = time.perf_counter_ns()

    def clear(self):
        """
        Очистити часові мітки.
        """
        for i in range(self.STEP_COUNT):
            self.timestamps[i] = 0

            