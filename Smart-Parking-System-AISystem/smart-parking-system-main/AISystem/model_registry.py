"""
model_registry.py
-----------------
Loads CLIP and OSNet exactly once per process and shares them across
every VehicleTracker instance.  Thread-safe via a module-level lock.
"""
import os

import torch.nn as nn
import threading
import torch
from transformers import CLIPModel, CLIPProcessor
import torchreid
from torchvision import models
from ultralytics import YOLO
import torchvision.models as tv_models


class _ModelRegistry:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        # Double-checked locking so the heavy model loads happen only once
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def initialize(self, device: str = None):
        if self._initialized:
            return

        with self._lock:
            if self._initialized:   # re-check inside lock
                return

            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
             clip_path = r"F:\Graduation project\Smart-Parking-System-AISystem\Smart-Parking-System-AISystem\smart-parking-system-main\AISystem\Models\clip_local"  # The folder where you saved the model

            if os.path.exists(clip_path):
                print(f"[ModelRegistry] Loading CLIP from LOCAL DISK: {clip_path}")
                self.clip_model = CLIPModel.from_pretrained(clip_path)
                self.clip_processor = CLIPProcessor.from_pretrained(clip_path)
                print(f"[ModelRegistry] Loading CLIP on {self.device}…")
            else:
                print(f"[ModelRegistry] Local CLIP not found. Downloading from HuggingFace...")
                self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

            self.clip_model.eval().to(self.device)

            print(f"[ModelRegistry] Loading OSNet on {self.device}…")
            self.reid_model = torchreid.models.build_model(
                name="osnet_x1_0", num_classes=1000, pretrained=True
            )
            self.reid_model.eval().to(self.device)

            # self.color_model = models.mobilenet_v2(weights=None)
            #
            # num_ftrs = self.color_model.classifier[1].in_features
            # self.color_model.classifier[1] = nn.Sequential(
            #     nn.Dropout(0.3),
            #     nn.Linear(num_ftrs, 15)  # Ensure this matches your number of classes
            # )
            #
            # # 2. Load the Saved Weights
            # self.color_model.load_state_dict(torch.load('../car_color_refined.pth', map_location=device))
            # self.color_model.to(self.device)
            # self.color_model.eval()
            print("[ModelRegistry] Loading Color Model...")

            self.color_model = tv_models.efficientnet_b0(weights=None)

            num_ftrs = self.color_model.classifier[1].in_features
            self.color_model.classifier[1] = nn.Linear(num_ftrs, 10)
            #
            # weights_path = os.path.join(
            #     os.path.dirname(__file__),
            #     "./tracknav/car_color_efficientnet.pth"
            # )
            #
            # if not os.path.exists(weights_path):
            #     raise FileNotFoundError(
            #         f"Color model weights not found: {weights_path}"
            #     )
            #
            # self.color_model.load_state_dict(
            #     torch.load(weights_path, map_location=self.device)
            # )

            self.color_model.to(self.device)
            self.color_model.eval()

            print("[ModelRegistry] Loading YOLO Segmentation...")

            self.yolo = YOLO("yolov8s-seg.pt")

            # optional: move to device (ultralytics handles internally)
            try:
                self.yolo.to(self.device)
            except:
                pass
            self.brand_model = YOLO('yolov8n-cls.pt')

            self._initialized = True
            print("[ModelRegistry] All models ready.")



# Public singleton accessor
ModelRegistry = _ModelRegistry()