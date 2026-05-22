import cv2
import numpy as np
from ultralytics import YOLO

from AISystem.APIClient import APIClient
from datetime import datetime
from collections import Counter

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

        self.api = APIClient(backend_url)

    # =========================

    def calculate_sharpness(self, image):

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        lap = cv2.Laplacian(gray, cv2.CV_64F)

        return lap.var()

    # =========================
    # def get_embedding(self,image):
    #     color_coverted = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    #     pil_image = Image.fromarray(color_coverted)
    #     model = resnet50(weights=ResNet50_Weights.DEFAULT)
    #     model = torch.nn.Sequential(*(list(model.children())[:-1]))  # Strips the last layer
    #     model.eval()
    #     preprocess = T.Compose([
    #         T.Resize((224, 224)),
    #         T.ToTensor(),
    #         T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    #     ])
    #     input_tensor = preprocess(pil_image).unsqueeze(0)

    #     with torch.no_grad():
    #         embedding = model(input_tensor)
    #     return embedding.flatten().numpy()

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

    # ========================

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
    def predict_color(self,image):
        # recognizer = CarColorRecognizer()
        # color = recognizer.predict(image)
        details = CarDetails()
        return details.get_car_details(image)




    def process_results(self, frame, results):

        # if self.should_enhance():
        #     frame = self.enhance_plate(frame)

        if results[0].boxes.id is None:
            return

        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.cpu().numpy().astype(int)

        roi_polygon = self.get_roi_polygon()

        for box, track_id in zip(boxes, track_ids):

            x1, y1, x2, y2 = map(int, box)


            cx = (x1 + x2) // 2
            cy = y2

            if cv2.pointPolygonTest(roi_polygon, (cx, cy), False) < 0:
                continue

            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

            crop = frame[y1:y2, x1:x2]



            if track_id not in self.frame_buffers:
                self.frame_buffers[track_id] = []

            self.frame_buffers[track_id].append(crop.copy())

            if len(self.frame_buffers[track_id]) > 10:
                self.frame_buffers[track_id].pop(0)
            if track_id not in self.color_buffers:
                self.color_buffers[track_id] = []

            crop_area = (x2 - x1) * (y2 - y1)
            if crop_area > 15000 and len(self.color_buffers[track_id]) < 5:
                color = self.predict_color(crop)
                self.color_buffers[track_id].append(color)

            current_position = self.is_crossing_line(
                (cx, cy),
                self.start_trigger,
                self.end_trigger
            )

            previous_position = self.previous_side.get(track_id)

            if previous_position is not None:


                if previous_position * current_position < 0:
                    if track_id not in self.processed_ids:

                        best_frame = self.get_best_frame(track_id)

                        if best_frame is not None:
                            plate = self.detect_and_draw_plate(best_frame)
                            vehicle_colors = self.color_buffers.get(track_id, ["Unknown"])
                            print(vehicle_colors)
                            most_common_color = Counter(vehicle_colors).most_common(1)[0][0]

                            if plate =='':
                                plate = 'None'
                            # embedding = self.get_embedding(best_frame)
                            # print("Embedding:", embedding)
                            self.api.send_async(self.api.send_to_backend,best_frame, plate,most_common_color)


                        self.processed_ids.add(track_id)

            self.previous_side[track_id] = current_position