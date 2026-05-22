
import cv2


import numpy as np
import time

from Threads.CameraThread import CameraThread
from Threads.DetectionThread import DetectionThread
from gates.BaseGate import BaseGate

class ExitGate(BaseGate):

    def __init__(self, source, car_model_path,plate_model_path,plate_recognition_path , backend_url=None):

        super().__init__(source, car_model_path,plate_model_path,plate_recognition_path, backend_url)
        self.start_left = (1, 396)
        self.end_left = (542, 173)

        self.start_right = (947, 495)
        self.end_right = (946, 194)

        self.start_trigger =  (359, 251)
        self.end_trigger = (946, 312)

    def get_roi_polygon(self):

        return np.array([
            self.start_left,
            self.end_left,
            self.end_right,
            self.start_right
        ], dtype=np.int32)

    def draw_lines(self, frame):

        cv2.line(frame, self.start_left, self.end_left, (0,255,0),2)
        cv2.line(frame, self.start_right, self.end_right, (0,255,0),2)

        cv2.line(frame, self.start_trigger, self.end_trigger, (0,0,255),3)

    def run(self):

        camera = CameraThread(self)
        detection = DetectionThread(self)

        camera.start()
        detection.start()
        fps = 30
        while self.running:

            if self.output_frame is not None:

                frame = self.output_frame.copy()

                self.draw_lines(frame)

                cv2.imshow("Exit Gate", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):   # pause / resume
              paused = not paused

            if key == 27:  # ESC
              self.running = False
              break
            time.sleep(1 / fps)

        camera.join()
        detection.join()

        cv2.destroyAllWindows()