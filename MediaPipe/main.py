import os
os.environ['GLOG_minloglevel'] = '2'

"""
main.py

Керування поглядом аватара VRChat
за допомогою MediaPipe Pose.

Клавіші

    1 - калібрування
    R - reset
    ESC - вихід
"""

import math
import time
import winsound
import threading

import cv2
import mediapipe as mp

from mediapipe_adapter import create_pose_frame
from calibration import Calibration
from body_tracker import BodyTracker
from look_controller import LookController
from grabcontroller import GrabController
from osc_sender import OSCSender


# ============================================================
# Camera
# ============================================================

from camera_reader import CameraReader

camera = CameraReader(0)

camera.start()

#----

import time

while True:

    success, frame = camera.read()

    if success:

        break

    time.sleep(0.01)


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

look_controller = LookController()

osc = OSCSender()

grab_controller = GrabController(osc)


# ============================================================
# Time
# ============================================================

previous_time = time.time()


# ============================================================
# Calibration
# ============================================================

CALIBRATION_TIME = 4.0

calibrating = False

calibration_start = 0.0

sum_yaw_metric = 0.0

sum_pitch_metric = 0.0

sample_count = 0

def calibration_countdown():
    """
    Програвання зворотного відліку калібрування.
    """
    print("Режим калібрування. Тримайте тіло у стані спокою впродовж декількох секунд")
    for i in range(3, 0, -1):
        print(f"{i}.......")
        if i == 1:
            winsound.Beep(1000, 700) # Final beep for 1
        else:
            winsound.Beep(1000, 200) # Short beeps for 3 and 2
        time.sleep(1)


# ============================================================
# Main
# ============================================================

print("------------------------------------")
print("VRChat Body Tracker")
print()
print("1 - calibration")
print("R - reset")
print("ESC - quit")
print("------------------------------------")


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

    elapsed = 0.0

    if results.pose_landmarks:

        #
        # Grab Controller
        #
        right_wrist = results.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_WRIST]
        grab_controller.update(right_wrist)

        #
        # Малювання лише ключових точок
        #
        h, w, _ = frame.shape
        landmark_indices = [
            mp_pose.PoseLandmark.NOSE,
            mp_pose.PoseLandmark.LEFT_SHOULDER,
            mp_pose.PoseLandmark.RIGHT_SHOULDER,
            mp_pose.PoseLandmark.RIGHT_WRIST,
        ]

        for index in landmark_indices:
            landmark = results.pose_landmarks.landmark[index]
            if landmark.visibility > 0.5:
                # We need to flip the x-coordinate for drawing
                cx = int((1 - landmark.x) * w)
                cy = int(landmark.y * h)
                cv2.circle(frame, (cx, cy), 10, (0, 255, 0), cv2.FILLED)
                
                # Display coordinates vertically
                cv2.putText(frame, f"x={landmark.x:.2f}", (cx - 50, cy + 25), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                cv2.putText(frame, f"y={landmark.y:.2f}", (cx - 50, cy + 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                cv2.putText(frame, f"z={landmark.z:.2f}", (cx - 50, cy + 55), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

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

        if calibrating:

            sum_yaw_metric += yaw_metric
            sum_pitch_metric += pitch_metric
            sample_count += 1
            elapsed = current_time - calibration_start

            if elapsed >= CALIBRATION_TIME:
                calibration.set_neutral(
                    sum_yaw_metric / sample_count,
                    sum_pitch_metric / sample_count
                )
                look_controller.reset()
                osc.center()
                calibrating = False

                print()
                print("Calibration completed.")
                calibration.print()

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
            look_horizontal = 0.0
            look_vertical = 0.0

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"Yaw Metric: {yaw_metric:.3f}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"Pitch Metric: {pitch_metric:.3f}",
            (10, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"LookH: {look_horizontal:.2f}",
            (10, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"LookV: {look_vertical:.2f}",
            (10, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

        if calibrating:

            cv2.putText(
                frame,
                "CALIBRATION...",
                (10, 190),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
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
    # Show camera
    # --------------------------------------------------------

    cv2.imshow(
        "VRChat Body Tracker",
        frame
    )

    # --------------------------------------------------------
    # Keyboard
    # --------------------------------------------------------

    key = cv2.waitKey(1)

    # ESC ----------------------------------------------------

    if key == 27:

        break

    # C ------------------------------------------------------

    elif key == ord("1"):

        if not calibrating:
            countdown_thread = threading.Thread(
                target=calibration_countdown
            )
            countdown_thread.start()

            calibrating = True

            calibration_start = time.time()

            sum_yaw_metric = 0.0
            sum_pitch_metric = 0.0
            sample_count = 0

    # R ------------------------------------------------------

    elif key == ord("r") or key == ord("R"):

        print()

        print("Reset.")

        calibration.reset()

        look_controller.reset()

        osc.center()

# ============================================================
# Shutdown
# ============================================================

print("Stopping...")

camera.stop()

cv2.destroyAllWindows()

pose.close()

osc.close()
