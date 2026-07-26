import time
import winsound
import numpy as np
import threading

class SmartCalibration:
    def __init__(self, data_collector, collection_duration=2):
        self._data_collector = data_collector
        self.collection_duration = collection_duration

    def run_calibration(self):
        """
        Runs the smart calibration process.
        """
        # print(f"DEBUG: run_calibration started. Thread ID: {threading.get_ident()}, Time: {time.time()}")
        print("Starting smart calibration...")
        
        duration_text = f"впродовж {self.collection_duration} секунд"

        # Step 1: Collect data for each position
        self._collect_data_for_position("neutral", f"Зафіксуйте смартфон у нейтральному стані {duration_text}")
        self._collect_data_for_position("forward", f"Зафіксуйте смартфон у крайньому положені під час руху \nВПЕРЕД")
        self._collect_data_for_position("backward", f"Зафіксуйте смартфон у крайньому положені під час руху \nНАЗАД")
        self._collect_data_for_position("left", f"Зафіксуйте смартфон у крайньому положені під час руху \nВЛІВО")
        self._collect_data_for_position("right", f"Зафіксуйте смартфон у крайньому положені під час руху\nВПРАВО")

        # Step 2: Analyze the data
        recommendations = self._analyze_data()

        # Step 3: Display recommendations
        self._display_recommendations(recommendations)

        return recommendations

    def _collect_data_for_position(self, position, message):
        """
        Collects data for a specific position.
        """
        # print(f"DEBUG: _collect_data_for_position for '{position}'. Thread ID: {threading.get_ident()}, Time: {time.time()}")
        print(message)
        for i in range(self.collection_duration, -1, -1):
            if i == 0:
                print(f"{i} ...")
                winsound.Beep(1000, 700)
            else:
                print(f"{i} ...")
                winsound.Beep(1000, 200)
            time.sleep(1)
        
        print("Збір даних:")
        self._data_collector.start_collecting(position)
        for i in range(self.collection_duration, 0, -1):
            print(f"{i} ...")
            winsound.Beep(1000, 200)
            time.sleep(1)
        self._data_collector.stop_collecting()
        print("0 .......") # Consistent message for final beep
        winsound.Beep(1000, 700) # Long beep after data collection

    def _analyze_data(self):
        """
        Analyzes collected data, returning recommended osc_bindings and new calibration values.
        """
        data = self._data_collector.get_data()
        
        # Calculate mean values for each position, ensuring not to process empty arrays
        mean_data = {pos: np.mean(arr, axis=0) for pos, arr in data.items() if arr}

        if "neutral" not in mean_data:
            print("Помилка: не вдалося зібрати дані для нейтрального стану.")
            return {"bindings": [], "calibration": {}}

        # --- New Calibration Values ---
        neutral_data = mean_data["neutral"]
        new_calibration = {
            "delta_accX": round(neutral_data[0], 2),
            "delta_accY": round(neutral_data[1], 2),
            "delta_accZ": round(neutral_data[2], 2)
        }

        # --- Axis Determination ---
        # Use absolute differences to find the dominant axis for each movement pair
        abs_diff_fwd = np.abs(mean_data["forward"] - mean_data["neutral"])
        abs_diff_bwd = np.abs(mean_data["backward"] - mean_data["neutral"])
        abs_diff_left = np.abs(mean_data["left"] - mean_data["neutral"])
        abs_diff_right = np.abs(mean_data["right"] - mean_data["neutral"])

        fb_axis_idx = np.argmax(abs_diff_fwd + abs_diff_bwd)
        lr_axis_idx = np.argmax(abs_diff_left + abs_diff_right)

        axis_map = {0: "X", 1: "Y", 2: "Z"}
        fb_axis = axis_map[fb_axis_idx]
        lr_axis = axis_map[lr_axis_idx]

        # --- Inversion Detection ---
        # Use signed differences to determine if inversion is needed
        signed_diff_fwd = mean_data["forward"][fb_axis_idx] - mean_data["neutral"][fb_axis_idx]
        signed_diff_left = mean_data["left"][lr_axis_idx] - mean_data["neutral"][lr_axis_idx]
        
        # MoveForward expects a positive change. If it's negative, we need to invert.
        fb_invert = signed_diff_fwd < 0
        
        # MoveLeft expects a negative change. If it's positive, we need to invert.
        lr_invert = signed_diff_left > 0

        # --- Build Recommendations ---
        bindings = []
        
        # Forward/Backward
        fwd_binding = {"osc_command": "/input/MoveForward", "axis": fb_axis}
        bwd_binding = {"osc_command": "/input/MoveBackward", "axis": fb_axis}
        if fb_invert:
            fwd_binding["invert"] = True
            bwd_binding["invert"] = True
        bindings.extend([fwd_binding, bwd_binding])

        # Left/Right
        left_binding = {"osc_command": "/input/MoveLeft", "axis": lr_axis}
        right_binding = {"osc_command": "/input/MoveRight", "axis": lr_axis}
        if lr_invert:
            left_binding["invert"] = True
            right_binding["invert"] = True
        bindings.extend([left_binding, right_binding])

        # Run (default)
        run_axis_candidate = f"{fb_axis}_{lr_axis}".replace(f"{lr_axis}_{fb_axis}", f"{fb_axis}_{lr_axis}") # consistent order
        bindings.append({"osc_command": "/input/Run", "axis": run_axis_candidate})

        return {"bindings": bindings, "calibration": new_calibration}

    def _display_recommendations(self, result):
        """
        Displays the recommended osc_bindings and calibration values.
        """
        if not result or not result.get("bindings"):
            print("Не вдалося створити рекомендації.")
            return
            
        print("\n--- Рекомендовані налаштування osc_bindings ---")
        for binding in result["bindings"]:
            line = f"{binding['osc_command']}: {binding['axis']}"
            if binding.get("invert"):
                line += ", invert: true"
            print(line)
        if "calibration" in result and result["calibration"]:
            cal = result["calibration"]
            print("--- Рекомендовані налаштування calibration ---")
            print(f"delta_accX: {cal['delta_accX']:.2f}")
            print(f"delta_accY: {cal['delta_accY']:.2f}")
            print(f"delta_accZ: {cal['delta_accZ']:.2f}")
            print("--------------------------------------------------")

class DataCollector:
    def __init__(self, smart_calibration_data, smart_calibration_state, SmartCalibrationState):
        self._smart_calibration_data = smart_calibration_data
        self._smart_calibration_state = smart_calibration_state
        self._SmartCalibrationState = SmartCalibrationState

    def start_collecting(self, position):
        state_map = {
            "neutral": self._SmartCalibrationState.COLLECTING_NEUTRAL,
            "forward": self._SmartCalibrationState.COLLECTING_FORWARD,
            "backward": self._SmartCalibrationState.COLLECTING_BACKWARD,
            "left": self._SmartCalibrationState.COLLECTING_LEFT,
            "right": self._SmartCalibrationState.COLLECTING_RIGHT,
        }
        self._smart_calibration_state.set(state_map[position])
    
    def stop_collecting(self):
        self._smart_calibration_state.set(self._SmartCalibrationState.IDLE)

    def get_data(self):
        return self._smart_calibration_data
