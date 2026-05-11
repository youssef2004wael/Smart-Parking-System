import queue

import cv2
import threading
import time

class CameraThread(threading.Thread):

    def __init__(self, gate):
        super().__init__()

        self.gate = gate
        self.cap = None
        self.fail_count = 0
        self.max_fail = 3

    # ============================

    def connect_camera(self):

        print("Connecting to AISystem...")

        # retries = 5
        retries = 1
        for attempt in range(retries):

            self.cap = cv2.VideoCapture(self.gate.source, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if self.cap.isOpened():
                print("AISystem connected successfully")
                return True

            print(f"Connection attempt {attempt+1} failed...")
            time.sleep(1)

        print("AISystem connection failed")
        self.cap = None
        return False

    # ============================

    def run(self):

        if not self.connect_camera():
            return

        while self.gate.running:

            ret, frame = self.cap.read()


            # =========================
            # corrupted frame
            # =========================

            if not ret or frame is None:

                self.fail_count += 1
                print("Corrupted frame... skipping")

                if self.fail_count >= self.max_fail:
                    print("Too many failures → reconnecting")

                    if self.cap:
                        self.cap.release()

                    time.sleep(1)

                    if not self.connect_camera():
                        break

                    self.fail_count = 0

                continue


            # =========================

            self.fail_count = 0

            # frame = cv2.resize(frame, (960, 540))
            #new changes
            # self.gate.frame = frame
            try:
                self.gate.frame_queue.put(frame, timeout=1)
            except queue.Full:
                continue
        if self.cap:
            self.cap.release()