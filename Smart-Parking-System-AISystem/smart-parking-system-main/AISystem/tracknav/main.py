import os
import threading
import cv2
import time
import numpy as np
import math
import gc
import queue

from AISystem.model_registry import ModelRegistry
from AISystem.tracknav.batch import BatchDetectionEngine
from AISystem.tracknav.camera_manager import get_shared_frame, get_camera_manager
from AISystem.tracknav.newTracking import VehicleTracker
from AISystem.EntranceExitGates.gates.EntranceGate import EntranceGate
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


def main():
    gc.collect()
    ModelRegistry.initialize(device="cuda")
    get_camera_manager()

    gate_ids = [2,4,5,6,7]

    engine = BatchDetectionEngine("yolov8n.pt", batch_size=5)
    engine.start()

    gates = [
        VehicleTracker(engine, c)
        for c in gate_ids
    ]

    entrance_gate = EntranceGate(
        source= r"videos/new/D2_day.mp4",
        car_model_path="../Models/car_detection/yolov8n.pt",
        plate_model_path="../Models/plate_detection/best.pt",
        plate_recognition_path="../Models/plate_recognition/best_arabic.pt",
        backend_url="http://72.62.6.246:8000/api/entry/"
    )

    ent_det_thread = DetectionThread(entrance_gate)
    ent_det_thread.start()

    window_name = "Smart Parking - Multi-Cam Async"
    cv2.namedWindow(window_name)
    cell_size = (500, 300)

    # shared_context بيحمل grid_positions والـ display_map
    shared_context = {
        "grid_positions": {},
        "display_map": {}   # idx في الـ grid → gate object
    }

    def on_mouse(event, x, y, flags, param):
        w, h = cell_size
        for idx, (x1, y1, x2, y2) in shared_context["grid_positions"].items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                gate = shared_context["display_map"].get(idx)
                if gate:
                    local_x = x - x1
                    local_y = y - y1
                    scale_x = 640 / w
                    scale_y = 360 / h
                    gate.mouse_callback(
                        event,
                        int(local_x * scale_x),
                        int(local_y * scale_y),
                        flags,
                        None
                    )
                break

    cv2.setMouseCallback(window_name, on_mouse)

    latest_ent_frame = None
    last_ent_frame = None

    try:
        while True:
            # جيب آخر فريم من الـ entrance
            try:
                latest_ent_frame = entrance_gate.result_queue.get_nowait()
                last_ent_frame = latest_ent_frame
            except (queue.Empty, AttributeError):
                pass

            # ابني display_list و display_map من الصفر كل فريم
            display_list = []
            display_map = {}  # idx → gate

            # الـ entrance أول حاجة (index 0) - مش gate فمش بنضيفه للـ map
            if last_ent_frame is not None:
                frame_to_show = last_ent_frame.copy()
                entrance_gate.draw_lines(frame_to_show)
                display_list.append(frame_to_show)

            # جيب فريمات الـ cameras
            current_frames = {}
            for gate in gates:
                data = get_shared_frame(int(gate.camera_id))
                if data:
                    frame, _ = data
                    current_frames[gate.camera_id] = cv2.resize(frame, (640, 360))

            # ضيف فريمات الـ gates مع الـ mapping الصح
            for gate in sorted(gates, key=lambda g: g.camera_id):
                raw_frame = current_frames.get(gate.camera_id)
                if raw_frame is not None:
                    processed = gate.process_frame(raw_frame.copy())
                    if processed is not None:
                        grid_idx = len(display_list)   # الـ index الحالي في الـ grid
                        display_map[grid_idx] = gate   # ربط الـ index بالـ gate
                        display_list.append(processed)

            # حدّث الـ shared_context
            shared_context["display_map"] = display_map

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