import threading
import cv2
import numpy as np
import requests
from sympy.codegen.ast import continue_

from AISystem.EntranceExitGates.CarDetails import CarDetails

import threading
class APIClient:

    def __init__(self, base_url):
        self.base_url = base_url
        self.HEADERS = {'X-Camera-Key': 'my_ultra_secure_camera_token_2026'}
    def send_to_entrance(self,image, plate_text,color):
        success, img_encoded = cv2.imencode(".jpg", image)
        if not success:
            print("❌ Failed to encode image")
            return

        files = {}

        data = {
            "license_plate": plate_text,
            "car_color": color,
            "camera_id": "CAM-01"
        }
        files["entry_image"] = (
            "image.jpg",
            img_encoded.tobytes(),
            "image/jpeg"
        )
        try:
            print(data)
            response = requests.post(
                self.base_url,
                files=files,
                data=data,
                headers=self.HEADERS
            )

            if response.status_code in (200, 201):
                print("✅ Sent to backend successfully")
            else:
                print("❌ Backend error:", response.text)
        except requests.exceptions.RequestException as e:
            print("❌ Request failed:", str(e))

     #change
    def send_to_exit(self,image, plate_text):
        success, img_encoded = cv2.imencode(".jpg", image)
        if not success:
            print("❌ Failed to encode image")
            return
        data = {
            "license_plate": plate_text,
            "camera_id": "CAM-08"
        }
        files = {"exit_image": (
            "image.jpg",
            img_encoded.tobytes(),
            "image/jpeg"
        )}
        try:
            print(data)
            response = requests.post(
                self.base_url,
                files=files,
                data=data,
                headers=self.HEADERS
            )

            if response.status_code in (200, 201):
                print("✅ Sent to backend successfully")
            else:
                print("❌ Backend error:", response.text)


        except requests.exceptions.RequestException as e:
            print("❌ Request failed:", str(e))

    def send_to_backend(self, image, plate_text,color):
        if image is None:
            print("No image to send")
            return

        if self.base_url.endswith("/entry/"):
            self.send_to_entrance(image,plate_text,color)

        elif self.base_url.endswith("/exit/"):
            self.end_to_exit(image,plate_text)

    def send_embeddings(self,embedding):
        base_url = "http://72.62.6.246:8000/api/update-perspective/"
        if embedding is None or len(embedding) == 0 :
            print("NO embeddings in send_embeddings method")
            return
        data = {
            "car_embedding": embedding,
            "camera_id": "CAM-02"
        }
        try:
            response = requests.post(
                base_url,
                json=data,
                headers=self.HEADERS
            )
            if response.status_code in (200, 201):
                print("✅ Embeddings Send"+response.text)
            else:
                print("❌ Backend error:", response.text)
        except requests.exceptions.RequestException as e:
            print("❌ Request failed:", str(e))
    def send_tracking_embeddings(self,color,embedding,camera_id):
        if embedding is None or len(embedding) == 0:
            return
        # if int(camera_id) ==2:
        #     self.send_async(self.send_embeddings,embedding)
        #     return
        payload = {
            "car_embedding": embedding,
            "camera_id": camera_id,
            "car_color": color.lower()
        }
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self.HEADERS
            )
            if response.status_code in (200, 201):
                print("✅ Matched"+response.text)
            else:
                print("❌ NO Matching Embeddings:", response.text)
        except requests.exceptions.RequestException as e:
            print("❌ Request failed:", str(e))



    def send_async(self, func, *args):
        """Helper to run any API method in the background."""
        # #region agent log
        # log_debug(
        #     hypothesis_id="H3_THREAD_EXPLOSION",
        #     location="APIClient.py:send_async",
        #     message="Spawning async API thread",
        #     data={
        #         "target_func": getattr(func, "__name__", "unknown"),
        #         "active_threads_before": threading.active_count(),
        #     },
        # )
        # #endregion
        thread = threading.Thread(target=func, args=args, daemon=True)
        thread.start()

    # Example usage in VehicleTracker or main:
    # self.api.send_async(self.api.send_tracking_embeddings, color, emb, cam_id)
