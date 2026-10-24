"""
hand_gesture.py

Жест пальців правої кисті -> /input/UseRight (ПКМ).

MediaPipe Pose не бачить пальців, тому тут додатково працює MediaPipe Hands,
але лише на невеликому кропі навколо правого зап'ястя (і лише коли воно у
кадрі). Це дешевше, ніж Hands на весь кадр, і надійніше на малих кистях.

Режими жесту:
    "pinch" - щипок (великий + вказівний). Стабільніший, рекомендований.
    "curl"  - зігнутий вказівний палець.
"""

import math

import cv2
import mediapipe as mp

WRIST, THUMB_TIP, INDEX_PIP, INDEX_TIP, MIDDLE_MCP = 0, 4, 6, 8, 9

# (поріг "увімкнути", поріг "вимкнути") - гістерезис проти брижі.
THRESHOLDS = {
    "pinch": (0.35, 0.50),   # відстань(4,8) у площині кадру / розмір долоні
    "curl": (0.90, 1.15),    # відстань(8,0) / відстань(6,0)
}


def _dist(a, b) -> float:
    return math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))


def _dist_xy(a, b) -> float:
    """Відстань у площині кадру (без z: глибину Hands оцінює неточно)."""
    return math.hypot(a.x - b.x, a.y - b.y)


def gesture_ratio(lm, mode: str) -> float:
    """Менше значення = жест виражений сильніше. lm - 21 точка Hands."""
    if mode == "pinch":
        palm = _dist(lm[WRIST], lm[MIDDLE_MCP])
        return _dist_xy(lm[THUMB_TIP], lm[INDEX_TIP]) / max(palm, 1e-6)
    if mode == "curl":
        ref = _dist(lm[INDEX_PIP], lm[WRIST])
        return _dist(lm[INDEX_TIP], lm[WRIST]) / max(ref, 1e-6)
    raise ValueError(f"unknown gesture mode: {mode}")


class GestureState:
    """Гістерезис + підтвердження N кадрів. Не залежить від MediaPipe."""

    def __init__(self, mode="pinch", confirm_frames=2, release_frames=2):
        self.mode = mode
        self.on_thr, self.off_thr = THRESHOLDS[mode]
        self.confirm_frames = confirm_frames
        self.release_frames = release_frames
        self.active = False
        self._on = 0
        self._off = 0

    def update(self, ratio):
        """ratio=None означає 'кисть не знайдена' (рахується як відпущено)."""
        if self.active:
            released = ratio is None or ratio > self.off_thr
            self._off = self._off + 1 if released else 0
            if self._off >= self.release_frames:
                self.active, self._off, self._on = False, 0, 0
        else:
            pressed = ratio is not None and ratio < self.on_thr
            self._on = self._on + 1 if pressed else 0
            if self._on >= self.confirm_frames:
                self.active, self._on, self._off = True, 0, 0
        return self.active


class HandUseGesture:
    def __init__(self, mode="pinch", crop_shoulder_factor=1.6, min_crop_px=96):
        self.state = GestureState(mode)
        self.mode = mode
        self.crop_shoulder_factor = crop_shoulder_factor
        self.min_crop_px = min_crop_px
        # 21 точка кисті в пікселях повного (невіддзеркаленого) кадру
        self.last_points = None
        self.last_ratio = None
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=True,      # кроп "стрибає", тому без трекінгу
            max_num_hands=1,
            model_complexity=0,
            min_detection_confidence=0.5,
        )

    def reset(self):
        self.last_points = None
        self.last_ratio = None
        return self.state.update(None)

    def update(self, rgb, wrist, left_shoulder, right_shoulder) -> bool:
        """
        rgb - кадр RGB (не віддзеркалений), wrist - RIGHT_WRIST з Pose,
        плечі - з Pose (для масштабу кропу). Повертає: жест активний?
        """
        ratio = None
        self.last_points = None
        self.last_ratio = None
        if rgb is not None and wrist is not None:
            ratio = self._measure(rgb, wrist, left_shoulder, right_shoulder)
        self.last_ratio = ratio
        return self.state.update(ratio)

    def _measure(self, rgb, wrist, ls, rs):
        h, w, _ = rgb.shape
        shoulder_px = math.hypot((ls.x - rs.x) * w, (ls.y - rs.y) * h)
        side = int(max(shoulder_px * self.crop_shoulder_factor, self.min_crop_px))
        cx, cy = int(wrist.x * w), int(wrist.y * h)
        x0, y0 = max(cx - side // 2, 0), max(cy - side // 2, 0)
        x1, y1 = min(x0 + side, w), min(y0 + side, h)
        if x1 - x0 < 32 or y1 - y0 < 32:
            return None
        crop = rgb[y0:y1, x0:x1]
        res = self.hands.process(crop)
        # world-координати в метрах: не залежать від пропорцій кадру
        if not res.multi_hand_world_landmarks:
            return None
        # точки для малювання: кроп -> координати повного кадру
        cw, ch = x1 - x0, y1 - y0
        self.last_points = [
            (x0 + p.x * cw, y0 + p.y * ch)
            for p in res.multi_hand_landmarks[0].landmark
        ]
        return gesture_ratio(res.multi_hand_world_landmarks[0].landmark, self.mode)

    def draw(self, display_frame, mirrored=True, show_ratio=False):
        """Малює скелет кисті. mirrored=True, якщо кадр вже віддзеркалений."""
        if self.last_points is None:
            return
        h, w = display_frame.shape[:2]
        pts = [
            (int((w - x) if mirrored else x), int(y))
            for x, y in self.last_points
        ]
        color = (0, 255, 255) if self.state.active else (0, 255, 0)
        for a, b in mp.solutions.hands.HAND_CONNECTIONS:
            cv2.line(display_frame, pts[a], pts[b], color, 2)
        for pt in pts:
            cv2.circle(display_frame, pt, 3, (0, 0, 255), cv2.FILLED)
        if show_ratio and self.last_ratio is not None:
            txt = f"{self.mode}: {self.last_ratio:.2f} (on<{self.state.on_thr})"
            cv2.putText(display_frame, txt, (pts[0][0] - 60, pts[0][1] + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

    def close(self):
        self.hands.close()