import cv2
import numpy as np
from ultralytics import YOLO

from AISystem.APIClient import APIClient
from datetime import datetime

from AISystem.EntranceExitGates.CarDetails import CarDetails


class BaseGate:

    def __init__(self,
                 source,
                 car_model_path,
                 plate_model_path,
                 plate_recognition_path,
                 backend_url
                 ):

        self.source = source
        self.running = True

        self.frame = None
        self.output_frame = None
        self.color_buffers = {}

        self.car_model = YOLO(car_model_path)
        self.plate_model = YOLO(plate_model_path)
        self.plate_recognition = YOLO(plate_recognition_path)
        self.previous_side = {}
        self.processed_ids = set()
        self.frame_buffers = {}
        self.color_buffers = {}
        self.color_collect_started = {}

        self.color_trigger_margin = 60

        self.api = APIClient(backend_url)

    # =========================
    def point_to_line_distance(self, point, line_start, line_end):

        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end

        numerator = abs(
            (y2 - y1) * px -
            (x2 - x1) * py +
            x2 * y1 -
            y2 * x1
        )

        denominator = np.sqrt(
            (y2 - y1) ** 2 +
            (x2 - x1) ** 2
        )

        if denominator == 0:
            return 9999

        return numerator / denominator

    def calculate_sharpness(self, image):

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        lap = cv2.Laplacian(gray, cv2.CV_64F)

        return lap.var()

    def get_best_frame(self, track_id):

        if track_id not in self.frame_buffers:
            return None

        frames = self.frame_buffers[track_id]

        best_crop = None
        best_score = -1

        for img in frames:

            score = self.calculate_sharpness(img)

            if score > best_score:
                best_score = score
                best_crop = img

        del self.frame_buffers[track_id]

        return best_crop

    # =========================

    def is_crossing_line(self, point, line_start, line_end):

        x, y = point
        x1, y1 = line_start
        x2, y2 = line_end

        return (x-x1)*(y2-y1) - (y-y1)*(x2-x1)

    # =========================

    def recognize_plate(self, plate_crop, frame, abs_x1, abs_y1):

        ocr_results = self.plate_recognition(plate_crop, verbose=False)
        plate_text = ""

        for ocr_res in ocr_results:

            if ocr_res.boxes is None:
                continue

            chars = ocr_res.boxes.data.tolist()
            chars.sort(key=lambda x: x[0], reverse=True)

            for char in chars:
                cls_id = int(char[5])
                plate_text += str(ocr_res.names[cls_id]) + " "

        return plate_text
    def detect_and_draw_plate(self, frame):

        plate_results = self.plate_model(frame, verbose=False)

        for r in plate_results:
            for box in r.boxes:

                px1, py1, px2, py2 = map(int, box.xyxy[0])

                if px2 <= px1 or py2 <= py1:
                    continue

                plate_crop = frame[py1:py2, px1:px2]
                if plate_crop.size == 0:
                    continue

                # cv2.rectangle(frame,
                #               (px1, py1),
                #               (px2, py2),
                #               (0, 255, 0), 2)

                plate_text = self.recognize_plate(
                    plate_crop, frame, px1, py1
                )

                return plate_text

        return "None"

    def enhance_plate(self, plate_crop):
        lab = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        enhanced = cv2.merge((cl, a, b))
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        enhanced = cv2.GaussianBlur(enhanced, (3,3), 0)

        gamma = 1.3
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        enhanced = cv2.LUT(enhanced, table)

        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        enhanced = cv2.filter2D(enhanced, -1, kernel)

        return enhanced

    def should_enhance(self):
        current_hour = datetime.now().hour
        return current_hour >= 19 or current_hour < 6

    def predict_color(self, image):

        details = CarDetails()
        color, confidence = details.get_car_details(image)

        return color, confidence

    def get_weighted_color(self, track_id):

        if track_id not in self.color_buffers:
            return "Unknown"

        scores = {}

        for color, confidence in self.color_buffers[track_id]:

            if color not in scores:
                scores[color] = 0

            scores[color] += confidence

        if not scores:
            return "Unknown"

        final_color = max(scores, key=scores.get)

        return final_color



    def trigger_gate_action(self, track_id):
        self.processed_ids.add(track_id)

        plate = 'None'
        best_frame = None

        # Check if we buffered a high-quality pre-emptive plate read
        if track_id in self.best_plates_so_far:
            plate = self.best_plates_so_far[track_id]['plate']
            best_frame = self.best_plates_so_far[track_id]['frame']
        else:
            # Fallback to absolute sharpest buffered frame if text reading failed during approach
            best_frame = self.get_best_frame(track_id)
            if best_frame is not None:
                plate = self.detect_and_draw_plate(best_frame)

        if not plate or plate.strip() == '':
            plate = 'None'

        most_common_color = self.get_weighted_color(track_id)

        if best_frame is not None:
            print(f"🚀 [GATE API] Dispatching ID {track_id} | Plate: {plate} | Color: {most_common_color}")
            self.api.send_to_backend(best_frame, plate, most_common_color)

    def process_results(self, frame, results):
        if results[0].boxes.id is None:
            return

        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.cpu().numpy().astype(int)
        roi_polygon = self.get_roi_polygon()

        # Initialize dictionaries in your init if not present
        if not hasattr(self, 'best_plates_so_far'):
            self.best_plates_so_far = {}
        if not hasattr(self, 'has_crossed_trigger'):
            self.has_crossed_trigger = {}

        active_ids = set(track_ids)

        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = map(int, box)

            # Using bottom center for intersection line tracking
            cx = (x1 + x2) // 2
            cy = y2

            # Check if vehicle is inside valid processing zone
            if cv2.pointPolygonTest(roi_polygon, (cx, cy), False) < 0:
                continue

            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            crop = frame[y1:y2, x1:x2]

            # 1. Maintain Frame Buffer for Sharpness
            if track_id not in self.frame_buffers:
                self.frame_buffers[track_id] = []
            self.frame_buffers[track_id].append(crop.copy())
            if len(self.frame_buffers[track_id]) > 10:
                self.frame_buffers[track_id].pop(0)

            # 2. Maintain Color Buffers
            if track_id not in self.color_buffers:
                self.color_buffers[track_id] = []

            # Measure spatial relationship to line
            distance = self.point_to_line_distance((cx, cy), self.start_trigger, self.end_trigger)
            current_side = self.is_crossing_line((cx, cy), self.start_trigger, self.end_trigger)

            # Convert cross product sign to standard state (1 or -1)
            current_state = 1 if current_side >= 0 else -1

            # 3. Active Capturing Zone (While approaching or near trigger)
            if distance < self.color_trigger_margin:
                # Capture Color data early
                if len(self.color_buffers[track_id]) < 15:
                    color, confidence = self.predict_color(crop)
                    self.color_buffers[track_id].append((color, confidence))

                # Active Plate Recognition buffering: continually update with the cleanest image available
                current_plate = self.detect_and_draw_plate(crop)
                if current_plate and current_plate != "None" and current_plate.strip() != "":
                    # If we don't have a plate yet, or if the current crop is sharper than our saved one
                    if track_id not in self.best_plates_so_far or self.calculate_sharpness(
                            crop) > self.calculate_sharpness(self.best_plates_so_far[track_id]['frame']):
                        self.best_plates_so_far[track_id] = {
                            'plate': current_plate,
                            'frame': crop.copy()
                        }

            # 4. Robust Trigger Evaluation
            previous_state = self.previous_side.get(track_id)

            if previous_state is not None and previous_state != current_state:
                # Sign flip occurred! Car crossed the threshold line
                if track_id not in self.processed_ids:
                    self.trigger_gate_action(track_id)

            # Save historical state
            self.previous_side[track_id] = current_state

        # ==================================================================
        # CRITICAL SAFETY CLEANUP FOR SHORT LINES & EDGE DROPOUTS
        # ==================================================================
        # If a car was tracked, inside our margin zone, but disappears from the frame
        # tracking array before a clean mathematical crossing equation is met.
        for tracked_id in list(self.previous_side.keys()):
            if tracked_id not in active_ids:
                # Car dropped out of frame pipeline completely
                if tracked_id not in self.processed_ids:
                    # Did we capture a valid plate while it was in our buffer zone?
                    if tracked_id in self.best_plates_so_far:
                        print(f"[Safety Trigger]: ID {tracked_id} lost near line boundary. Forcing API call.")
                        self.trigger_gate_action(tracked_id)

                # Clean up memory allocation maps for dead tracks
                self.previous_side.pop(tracked_id, None)
                self.best_plates_so_far.pop(tracked_id, None)