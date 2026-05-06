import json
import threading
import cv2
import time
import os


class CameraManager:
    FRAME_WIDTH = 960
    FRAME_HEIGHT = 540
    def __init__(self,json_path):
        # cam_id -> (frame, timestamp)
        self.json_path = json_path
        self.camera_configs = self._load_config()
        self.frames = {}
        self.locks = {cam_id: threading.Lock() for cam_id in self.camera_configs.keys()}
        self.running = True


    def _load_config(self):
        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
                # تحويل المفاتيح لـ strings أو integers حسب حاجتك، هنا هنستخدمها كـ keys
                return data
        except Exception as e:
            print(f"[ERROR] Failed to load JSON config: {e}")
            return {}
    def start_all(self):
        if not self.camera_configs:
            print("[ERROR] No cameras found in config.")
            return

        for cam_id, config in self.camera_configs.items():
            source = config['source']
            t = threading.Thread(
                target=self._reader,
                args=(cam_id, source),
                daemon=True
            )
            t.start()

        print(f"[SYSTEM] Camera Manager Active ({len(self.camera_configs)} cameras)")

    def _reader(self, cam_id, source):

        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        frame_counter = 0

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            print(f"[ERROR] Cannot open camera {cam_id}")

        frame_counter = 0
        try:
            while self.running:
                grabbed = cap.grab()
                frame_counter += 1
                time.sleep(0.01)

                if frame_counter % 2 != 0:
                    continue

                if not grabbed:
                    print(f"[RECONNECT] Cam {cam_id} lost... reconnecting")
                    cap.release()
                    time.sleep(1)
                    cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                    continue
                ret, frame = cap.retrieve()

                if not ret or frame is None:
                    continue

                frame = cv2.resize(frame, (self.FRAME_WIDTH, self.FRAME_HEIGHT))

                # ❗ Filter gray / corrupted frames
                if frame.mean() < 20:
                    print(f"[WARNING] Cam {cam_id} gray frame skipped")
                    continue

                # Save latest frame with timestamp
                with self.locks[cam_id]:
                    self.frames[cam_id] = (frame, time.time())
        except Exception as e:
            print(f"[CRASH] Camera {cam_id}: {e}")



    def get_frame(self, cam_id):
        cam_id = str(cam_id)
        lock = self.locks.get(cam_id)
        if lock:
            with lock:
                return self.frames.get(cam_id, None)
        return None


_cm_instance = None


def get_camera_manager(config_path="cameras_config.json"):
    global _cm_instance
    if _cm_instance is None:
        _cm_instance = CameraManager(config_path)
        _cm_instance.start_all()
    return _cm_instance

def get_shared_frame(cam_id):
    global _cm_instance
    if _cm_instance is not None:
        return _cm_instance.get_frame(cam_id)
    return None
