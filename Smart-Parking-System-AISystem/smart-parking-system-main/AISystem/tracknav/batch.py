import threading
from queue import Queue, Empty
from ultralytics import YOLO
import time
from AISystem.tracknav.gpu_worker import get_gpu_worker

class BatchDetectionEngine(threading.Thread):
    def __init__(self, model_path, batch_size=6, device="cuda"):
        super().__init__(daemon=True)
        self.model = YOLO(model_path)
        self.device = device
        self.batch_size = batch_size

        self.input_queue = Queue(maxsize=10)
        self.results = {}
        self.lock = threading.Lock()
        self.running = True

    # def submit_frame(self, cam_id, frame):
    #     if self.input_queue.full():
    #         try:
    #             self.input_queue.get_nowait()
    #         except Empty:
    #             pass
    #     self.input_queue.put((cam_id, frame))

    def submit_frame(self, cam_id, frame):
        if self.input_queue.full():
            try:
                self.input_queue.get_nowait()
            except Empty:
                pass
        self.input_queue.put((cam_id, frame.copy()))

    def get_result(self, cam_id):
        with self.lock:
            return self.results.get(cam_id)

    def run(self):
        while self.running:
            frames = []
            cam_ids = []

            while len(frames) < self.batch_size:
                try:
                    cam_id, frame = self.input_queue.get(timeout=0.01)
                    frames.append(frame)
                    cam_ids.append(cam_id)
                except Empty:
                    break

            if not frames:
                continue

            gpu = get_gpu_worker()

            q = gpu.submit(
            self.model.predict,
              frames,
              device=self.device,
              conf=0.5,
              iou=0.6,
              verbose=False,
              classes=[2,3,5,7]
              )

            results = q.get()
            time.sleep(0.005)

            with self.lock:
                for cam_id, res, f in zip(cam_ids, results, frames):
                    self.results[cam_id] = (f, res)