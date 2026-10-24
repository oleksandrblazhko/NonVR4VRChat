import os
os.environ['GLOG_minloglevel'] = '2'

"""
main.py

Керування поглядом аватара VRChat
за допомогою MediaPipe Pose.

Клавіші (обробка - в interface.py)

    1 - калібрування
    R - reset
    P / O - наступний / попередній профіль
    ESC - вихід
"""

import math
import time

import cv2
import mediapipe as mp

from mediapipe_adapter import create_pose_frame
from calibration import Calibration
from body_tracker import BodyTracker
from look_controller import LookController
from grabcontroller import GrabController
from grabcontroller import UseController
from hand_gesture import HandUseGesture
from osc_sender import OSCSender
from interface import Interface
from profiles import ProfileManager


# ============================================================
# Camera
# ============================================================

from camera_reader import CameraReader

camera = CameraReader()

camera.start()

# Перший кадр потрібен до циклу нижче; якщо камери немає,
# wait_first_frame() періодично пише про це в консоль.
success, frame = camera.wait_first_frame()


# ============================================================
# MediaPipe
# ============================================================

mp_pose = mp.solutions.pose

pose = mp_pose.Pose(

    static_image_mode=False,

    model_complexity=1,

    smooth_landmarks=True,

    enable_segmentation=False,

    min_detection_confidence=0.5,

    min_tracking_confidence=0.5

)

drawer = mp.solutions.drawing_utils


# ============================================================
# Modules
# ============================================================

calibration = Calibration()

tracker = BodyTracker(
    calibration
)

profiles = ProfileManager()

look_controller = LookController(profiles)

osc = OSCSender()

grab_controller = GrabController(osc)

use_controller = UseController(osc)

# ПКМ правою рукою: щипок ("pinch") або зігнутий вказівний ("curl").
right_use_controller = UseController(osc)
right_gesture = HandUseGesture(mode="pinch")

interface = Interface(
    calibration,
    look_controller,
    osc,
    profiles=profiles
)


# Shift/Ctrl + / - : чутливість LookH / LookV (глобальні хоткеї).
interface.start_hotkeys()


# ============================================================
# Time
# ============================================================

previous_time = time.time()


# ============================================================
# Main
# ============================================================

interface.print_banner()


while True:

    success, frame = camera.read()

    if not success:

        break

    # Process original frame
    rgb = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )
    results = pose.process(rgb)

    # Flip frame for display
    frame = cv2.flip(
        frame,
        1
    )

    current_time = time.time()

    dt = max(

        current_time -

        previous_time,

        1e-6

    )

    fps = 1.0 / dt

    previous_time = current_time

    if results.pose_landmarks:

        #
        # Hand gestures
        #
        right_wrist = results.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_WRIST]
        grab_controller.update(right_wrist)

        left_wrist = results.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_WRIST]
        use_controller.update(left_wrist)

        if right_wrist.visibility >= grab_controller.VISIBILITY_LIMIT:
            pinch = right_gesture.update(
                rgb,
                right_wrist,
                results.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_SHOULDER],
                results.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_SHOULDER],
            )
        else:
            pinch = right_gesture.reset()
        right_use_controller.update_active(pinch)

        #
        # Малювання лише ключових точок
        #
        h, w, _ = frame.shape
        landmark_indices = [
            mp_pose.PoseLandmark.NOSE,
            mp_pose.PoseLandmark.LEFT_EAR,
            mp_pose.PoseLandmark.RIGHT_EAR,
            mp_pose.PoseLandmark.LEFT_SHOULDER,
            mp_pose.PoseLandmark.RIGHT_SHOULDER,
            mp_pose.PoseLandmark.LEFT_WRIST,
            mp_pose.PoseLandmark.RIGHT_WRIST,
        ]

        for index in landmark_indices:
            landmark = results.pose_landmarks.landmark[index]
            if landmark.visibility > 0.5:
                # We need to flip the x-coordinate for drawing
                cx = int((1 - landmark.x) * w)
                cy = int(landmark.y * h)
                cv2.circle(frame, (cx, cy), 10, (0, 255, 0), cv2.FILLED)

        right_gesture.draw(frame)

        pose_frame = create_pose_frame(

            results.pose_landmarks,

            fps

        )

        state = tracker.update(
            pose_frame
        )

        yaw_metric = state.yaw_metric
        pitch_metric = state.pitch_metric

        # ----------------------------------------------------
        # Calibration
        # ----------------------------------------------------

        interface.update(
            yaw_metric,
            pitch_metric
        )

        # ----------------------------------------------------
        # Tracking
        # ----------------------------------------------------

        if calibration.is_ready():

            #
            # Перетворення у OSC.
            #

            look_horizontal, look_vertical = (
                look_controller.update(
                    yaw_metric,
                    pitch_metric,
                    calibration.neutral_yaw_metric,
                    calibration.neutral_pitch_metric
                )
            )

            osc.send_look(
                look_horizontal,
                look_vertical
            )

    else:

        cv2.putText(
            frame,
            "Pose not detected",
            (10, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

    # --------------------------------------------------------
    # Status & display
    # --------------------------------------------------------

    interface.draw_status(
        frame
    )

    if calibration.is_ready():
        disp_look_h = look_controller.horizontal
        disp_look_v = look_controller.vertical
    else:
        disp_look_h = None
        disp_look_v = None

    display_frame = interface.render_display(
        frame,
        look_horizontal=disp_look_h,
        look_vertical=disp_look_v,
        grab_state=grab_controller.grab_state,
        use_triggered=(use_controller.is_triggered
                       or right_use_controller.is_triggered),
    )

    # --------------------------------------------------------
    # Show camera
    # --------------------------------------------------------

    cv2.imshow(
        "VRChat Body Tracker",
        display_frame
    )

    # --------------------------------------------------------
    # Keyboard
    # --------------------------------------------------------

    interface.poll_hotkeys()

    if interface.handle_key(
            interface.read_key()
    ):

        break

# ============================================================
# Shutdown
# ============================================================

print("Stopping...")

interface.stop_hotkeys()

interface.save_settings()

osc.center()

camera.stop()

cv2.destroyAllWindows()

pose.close()

right_gesture.close()

osc.close()