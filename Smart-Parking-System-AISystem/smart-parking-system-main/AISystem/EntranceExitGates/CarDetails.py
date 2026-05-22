
import os
import cv2
import torch
import numpy as np
import torchreid
from PIL import Image
from sklearn.metrics.pairwise import cosine_similarity
from torchvision import transforms
from transformers import CLIPModel, CLIPProcessor
from ultralytics import YOLO
import torchvision.models as models

from AISystem.model_registry import ModelRegistry


class CarDetails:
    def __init__(self):

        # self.model = self.model.to(self.device)
        # self.yolo = YOLO("yolov8n-seg.pt")
        self.yolo = ModelRegistry.yolo
        self.color_model = ModelRegistry.color_model

        self.device = ModelRegistry.device
        self.clip_model = ModelRegistry.clip_model
        self.clip_processor = ModelRegistry.clip_processor
        self.car_colors = [
            "a black car", "a white car", "a silver car", "a gray car",
            "a red car", "a blue car", "a green car", "a beige car",
            "a brown car"
            , "an orange car", "a yellow car",
            "a purple car", "a pink car"
        ]
        self.brand_model = ModelRegistry.brand_model

        self.color_names = [c.replace("a ", "").replace("an ", "").replace(" car", "").title()
                            for c in self.car_colors]
        self.reid_model = ModelRegistry.reid_model

    def enhance_crop(self, img):

        # LAB color correction
        result = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

        avg_a = np.average(result[:, :, 1])
        avg_b = np.average(result[:, :, 2])

        result[:, :, 1] = result[:, :, 1] - (
                (avg_a - 128) * (result[:, :, 0] / 255.0) * 0.6
        )

        result[:, :, 2] = result[:, :, 2] - (
                (avg_b - 128) * (result[:, :, 0] / 255.0) * 0.6
        )

        result = cv2.cvtColor(result, cv2.COLOR_LAB2BGR)

        # mild brightness normalization
        result = cv2.convertScaleAbs(result, alpha=1.05, beta=5)

        return result

    def segment_car_with_mask(self, img):

        results = self.yolo(img, verbose=False)[0]

        if results.masks is None or len(results.masks.data) == 0:
            return img

        car_idx = None

        # COCO class 2 = car
        for i, cls in enumerate(results.boxes.cls):

            if int(cls) == 2:
                car_idx = i
                break

        if car_idx is None:
            return img

        # =========================================
        # Mask
        # =========================================
        mask = results.masks.data[car_idx].cpu().numpy()

        mask = cv2.resize(
            mask,
            (img.shape[1], img.shape[0])
        )

        binary_mask = (mask > 0.5).astype(np.uint8)

        # neutral gray background
        background = np.full_like(img, 127)

        inv_mask = cv2.bitwise_not(binary_mask * 255)

        car_part = cv2.bitwise_and(
            img,
            img,
            mask=binary_mask
        )

        bg_part = cv2.bitwise_and(
            background,
            background,
            mask=inv_mask
        )

        masked_img = cv2.add(car_part, bg_part)

        box = results.boxes.xyxy[car_idx].cpu().numpy().astype(int)

        x1, y1, x2, y2 = box

        cropped = car_part[y1:y2, x1:x2]

        if cropped.size == 0:
            return img

        h, w = cropped.shape[:2]

        if h > 224 and w > 224:
            cropped = cv2.resize(cropped, (224, 224))

        return self.enhance_crop(cropped)

    def get_cnn_color(self, img):
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                [0.485, 0.456, 0.406],
                [0.229, 0.224, 0.225]
            )
        ])

        tensor = transform(img_rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.color_model(tensor)
            pred = output.argmax(1).item()

        return self.color_names[pred]

    def detect_car_color(self,img_bgr):
        if img_bgr is None or img_bgr.size == 0:
            return "Unknown"

        h, w = img_bgr.shape[:2]

        # ── 1. Focus on body center (avoid roof, bumpers, shadow edges) ──────────
        y1, y2 = int(h * 0.15), int(h * 0.85)
        x1, x2 = int(w * 0.10), int(w * 0.90)
        roi = img_bgr[y1:y2, x1:x2]

        img_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        H, S, V = img_hsv[:, :, 0], img_hsv[:, :, 1], img_hsv[:, :, 2]

        # ── 2. Build a validity mask: exclude pure black pixels (shadows/tires) ──
        valid = V > 30  # ignore near-black shadow/tire pixels

        total = np.count_nonzero(valid)
        if total == 0:
            return "Unknown"

        # ── 3. Achromatic detection first (priority order) ───────────────────────
        # Black:  low brightness, any saturation
        black_mask = valid & (V <= 50)
        # Gray:   moderate brightness, very low saturation
        gray_mask = valid & (V > 50) & (V <= 200) & (S < 30)
        # Silver: moderate-high brightness, slight saturation (metallic sheen)
        silver_mask = valid & (V > 100) & (V <= 220) & (S >= 15) & (S < 55)
        # White:  high brightness, very low saturation
        white_mask = valid & (V > 200) & (S < 40)

        black_ratio = np.count_nonzero(black_mask) / total
        gray_ratio = np.count_nonzero(gray_mask) / total
        silver_ratio = np.count_nonzero(silver_mask) / total
        white_ratio = np.count_nonzero(white_mask) / total

        # ── 4. Chromatic color ranges (H-based, only on valid & saturated pixels) ─
        chromatic_mask = valid & (S >= 60)

        color_h_ranges = {
            "Red": [((0, 10), True), ((165, 180), True)],  # wraps around 0
            "Orange": [((10, 25), False)],
            "Yellow": [((25, 35), False)],
            "Green": [((35, 85), False)],
            "Blue": [((85, 130), False)],
            "Purple": [((130, 155), False)],
            "Pink": [((155, 165), False)],
        }

        chromatic_counts = {}
        for color_name, h_ranges in color_h_ranges.items():
            mask = np.zeros(H.shape, dtype=bool)
            for (h_lo, h_hi), _ in h_ranges:
                mask |= (H >= h_lo) & (H <= h_hi)
            mask &= chromatic_mask
            chromatic_counts[color_name] = np.count_nonzero(mask)

        best_chromatic = max(chromatic_counts, key=chromatic_counts.get)
        best_chromatic_ratio = chromatic_counts[best_chromatic] / total

        # ── 5. Decision: chromatic wins only if it's clearly dominant ────────────
        CHROMATIC_THRESHOLD = 0.20  # at least 20% of valid pixels

        if best_chromatic_ratio >= CHROMATIC_THRESHOLD:
            return best_chromatic

        # ── 6. Achromatic decision (priority: Black > White > Silver > Gray) ──────
        achromatic = {
            "Black": black_ratio,
            "White": white_ratio,
            "Silver": silver_ratio,
            "Gray": gray_ratio,
        }

        # Require a minimum ratio to avoid noise
        MIN_ACHROMATIC = 0.15
        dominant = max(achromatic, key=achromatic.get)

        if achromatic[dominant] >= MIN_ACHROMATIC:
            return dominant

        return "Unknown"

    def get_embedding(self, img) -> np.ndarray:
        """
        img: numpy BGR array OR PIL RGB image — handles both
        """
        # --- Unify input to RGB numpy array ---
        if isinstance(img, np.ndarray):
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # BGR → RGB
        elif isinstance(img, Image.Image):
            img = np.array(img.convert("RGB"))

        transform = transforms.Compose([
            transforms.ToPILImage(),  # expects HxWxC RGB uint8
            transforms.Resize((256, 128)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

        tensor = transform(img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            # ✅ Extract intermediate features, NOT classifier logits
            features = self.reid_model.featuremaps(tensor)  # spatial feature map
            features = torch.nn.functional.adaptive_avg_pool2d(features, 1)
            features = features.view(features.size(0), -1)

        emb = features.cpu().numpy().flatten()
        return emb / (np.linalg.norm(emb) + 1e-6)

    def getColor(self,image):
        img_rgb = cv2.cvtColor(image,  cv2.COLOR_BGR2RGB)
        inputs = self.clip_processor(text=self.car_colors, images=Image.fromarray(img_rgb), return_tensors="pt",
                                     padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.clip_model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)[0]
        color = self.color_names[probs.argmax().item()]
        return color

    def get_car_brand_yolo(self,bgr_image):

        results = self.brand_model.predict(source=bgr_image, verbose=False)

        top_class_index = results[0].probs.top1
        brand_name = results[0].names[top_class_index]

        return brand_name


    def get_car_details(self,image):
        try:
            color = self.getColor(image)
            # brand = self.get_car_brand_yolo(image)

            return color.lower()
        except Exception as e:
            print(f"Error getting car details: {e}")
            # Return default values
            return "Unknown", np.zeros(512)  # Adjust 2048 to match your ResNet output




