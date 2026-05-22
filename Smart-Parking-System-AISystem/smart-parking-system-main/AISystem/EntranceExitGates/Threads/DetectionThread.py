import threading
import time

import cv2

import threading
import queue

from AISystem.tracknav.camera_manager import get_shared_frame
from AISystem.tracknav.gpu_worker import get_entrance_worker


class DetectionThread(threading.Thread):
    def __init__(self, gate):
        super().__init__()
        self.gate = gate


    def run(self):
        print(f"DetectionThread for {self.gate.source} started.")
        gpu = get_entrance_worker()

        while self.gate.running:
            try:
                # frame = self.gate.frame_queue.get(timeout=1.0)

                # if frame is None:
                #     continue
                data = get_shared_frame(str(self.gate.cam_id))
                if data is None:
                    time.sleep(0.01)
                    continue

                frame, timestamp = data

                q = gpu.submit(
                    self.gate.car_model.track,
                    frame,
                    persist=True,
                    classes=[2],
                    conf=0.5,
                    verbose=False
                )

                results = q.get()

                self.gate.process_results(frame, results)
                # time.sleep(0.1)

                try:
                    if self.gate.result_queue.full():
                        self.gate.result_queue.get_nowait()
                    self.gate.result_queue.put(frame, block=False)
                except queue.Full:
                    pass

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in DetectionThread: {e}")
                continue

        print(f"DetectionThread for {self.gate.source} stopped.")