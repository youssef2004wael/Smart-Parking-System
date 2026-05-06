import queue

import cv2


import numpy as np

from AISystem.EntranceExitGates.Threads.CameraThread import CameraThread
from AISystem.EntranceExitGates.Threads.DetectionThread import DetectionThread
from AISystem.EntranceExitGates.gates.BaseGate import BaseGate
from AISystem.model_registry import ModelRegistry


class EntranceGate(BaseGate):

    def __init__(self, source, car_model_path,plate_model_path,plate_recognition_path , backend_url=None):

        super().__init__(source, car_model_path,plate_model_path,plate_recognition_path, backend_url)

        self.frame_queue = queue.Queue(maxsize=1)
        self.result_queue = queue.Queue(maxsize=1)
        self.cam_id = 1


        self.start_left = (4, 259)
        self.end_left = (595, 215)

        self.start_right =  (762, 533)
        self.end_right = (851, 273)

        self.start_trigger =(104, 253)
        self.end_trigger = (773, 496)


        # self.start_left = (5, 361)
        # self.end_left = (600, 140)
        #
        # self.start_right = (848, 531)
        # self.end_right = (871, 131)
        #
        # self.start_trigger = (227, 282)
        # self.end_trigger = (862, 392)
        # ModelRegistry.initialize()


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

        while self.running:

            if self.output_frame is not None:

                frame = self.output_frame.copy()

                self.draw_lines(frame)

                cv2.imshow("Entrance Gate", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):   # pause / resume
              paused = not paused

            if key == 27:  # ESC
              self.running = False
              break

        camera.join()
        detection.join()

        cv2.destroyAllWindows()