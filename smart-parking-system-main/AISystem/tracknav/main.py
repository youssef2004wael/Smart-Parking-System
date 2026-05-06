import os
import threading
import cv2
import time
import numpy as np
import math
import gc
import cv2

from AISystem.model_registry import ModelRegistry
from AISystem.tracknav.batch import BatchDetectionEngine
from AISystem.tracknav.camera_manager import get_shared_frame, get_camera_manager
from AISystem.tracknav.newTracking import VehicleTracker
from AISystem.EntranceExitGates.gates.EntranceGate import EntranceGate
from AISystem.EntranceExitGates.Threads.CameraThread import CameraThread
from AISystem.EntranceExitGates.Threads.DetectionThread import DetectionThread

def build_dynamic_grid(frames, cell_size=(500, 300)):
    if not frames:
        return None, 0, {}

    n = len(frames)
    cols = min(n, 3)
    rows = math.ceil(n / cols)

    w, h = cell_size
    grid_img = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)

    grid_positions = {}

    for idx, frame in enumerate(frames):
        r, c = divmod(idx, cols)

        x1, y1 = c * w, r * h
        x2, y2 = x1 + w, y1 + h

        resized = cv2.resize(frame, (w, h))
        grid_img[y1:y2, x1:x2] = resized

        grid_positions[idx] = (x1, y1, x2, y2)

    return grid_img, cols, grid_positions





def create_global_mouse_callback(gates, grid_positions, cell_size):
    def global_mouse(event, x, y, flags, param):
        w, h = cell_size

        for idx, (x1, y1, x2, y2) in grid_positions.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                gate = gates[idx]

                local_x = int((x - x1))
                local_y = int((y - y1))

                scale_x = gate.original_width / w
                scale_y = gate.original_height / h

                local_x = int(local_x * scale_x)
                local_y = int(local_y * scale_y)

                gate.mouse_callback(event, local_x, local_y, flags, None)
                break

    return global_mouse


import queue

def main():
    gc.collect()
    ModelRegistry.initialize(device="cuda")
    get_camera_manager()

    gate_ids = [2,3]

    # محرك الكشف للـ gates العادية
    engine = BatchDetectionEngine("yolov8n.pt", batch_size=5)
    engine.start()

    gates = [
        VehicleTracker(engine, c)
        for c in gate_ids
    ]

    entrance_gate = EntranceGate(
        source="D://first3vid/D02.mp4",
        car_model_path="../Models/car_detection/yolov8n.pt",
        plate_model_path="../Models/plate_detection/best.pt",
        plate_recognition_path="../Models/plate_recognition/best.pt",
        backend_url="http://127.0.0.1:8000/api/entry/"
    )

    # ent_cam_thread = CameraThread(entrance_gate)
    ent_det_thread = DetectionThread(entrance_gate)
    ent_det_thread.start()

    window_name = "Smart Parking - Multi-Cam Async"
    cv2.namedWindow(window_name)
    cell_size = (500, 300)
    shared_context = {"grid_positions": {}}

    # Mouse Callback (نفس المنطق القديم)
    def on_mouse(event, x, y, flags, param):
        w, h = cell_size
        for idx, (x1, y1, x2, y2) in shared_context["grid_positions"].items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                if idx < len(gates):
                    gate = gates[idx]
                    local_x, local_y = x - x1, y - y1
                    scale_x, scale_y = 640 / w, 360 / h
                    gate.mouse_callback(event, int(local_x * scale_x), int(local_y * scale_y), flags, None)
                break

    cv2.setMouseCallback(window_name, on_mouse)
    last_ent_frame = None

    try:
        while True:
            try:
                ent_frame_raw = entrance_gate.result_queue.get(block=False)
                last_ent_frame = ent_frame_raw.copy()
                entrance_gate.draw_lines(last_ent_frame)
            except (queue.Empty, AttributeError):
                pass

            current_frames = {}
            for gate in gates:
                data = get_shared_frame(int(gate.camera_id))
                if data:
                    frame, _ = data
                    current_frames[gate.camera_id] = cv2.resize(frame, (640, 360))

            # 3. تجميع كل الفريمات للعرض
            display_list = []

            # إضافة فريمات الـ Gates بعد معالجتها
            for gate in gates:
                raw_frame = current_frames.get(gate.camera_id)
                if raw_frame is not None:
                    processed = gate.process_frame(raw_frame.copy())
                    if processed is not None:
                        display_list.append(processed)

            if last_ent_frame is not None:
                display_list.append(last_ent_frame)
            if display_list:
                grid, cols, grid_positions = build_dynamic_grid(display_list, cell_size)
                shared_context["grid_positions"] = grid_positions
                cv2.imshow(window_name, grid)


            if cv2.waitKey(25) & 0xFF == ord('q'):
                break

    finally:
        print("Stopping system...")
        entrance_gate.running = False
        ent_det_thread.join()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
