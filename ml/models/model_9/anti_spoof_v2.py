import os
import sys
import cv2
import numpy as np
import torch
import torch.nn.functional as F

# Add the Silent-Face-Anti-Spoofing directory to the system path.
# Resolve robustly from env or this file location (not current working dir).
REPO_PATH = os.getenv(
    "MODEL9_REPO_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Silent-Face-Anti-Spoofing"),
)
if REPO_PATH not in sys.path:
    sys.path.append(REPO_PATH)

# Import the official models and utilities
from src.model_lib.MiniFASNet import MiniFASNetV1, MiniFASNetV2, MiniFASNetV1SE, MiniFASNetV2SE
from src.utility import get_kernel, parse_model_name
from src.generate_patches import CropImage

MODEL_MAPPING = {
    'MiniFASNetV1': MiniFASNetV1,
    'MiniFASNetV2': MiniFASNetV2,
    'MiniFASNetV1SE': MiniFASNetV1SE,
    'MiniFASNetV2SE': MiniFASNetV2SE
}

class AntiSpoofPredictor:
    def __init__(self, device_id=0):
        self.device = torch.device("cuda:{}".format(device_id) if torch.cuda.is_available() else "cpu")
        self.cropper = CropImage()
        self.models = []
        self.model_configs = []
        
        # Paths to official models in the repo
        model_dir = os.path.join(REPO_PATH, "resources", "anti_spoof_models")
        model_files = [
            "2.7_80x80_MiniFASNetV2.pth",
            "4_0_0_80x80_MiniFASNetV1SE.pth"
        ]
        
        for model_name in model_files:
            path = os.path.join(model_dir, model_name)
            if not os.path.exists(path):
                print(f"Warning: Model not found at {path}")
                continue
                
            # Parse config from filename
            h_input, w_input, model_type, scale = parse_model_name(model_name)
            kernel_size = get_kernel(h_input, w_input)
            
            # Instantiate official model
            model = MODEL_MAPPING[model_type](conv6_kernel=kernel_size).to(self.device)
            
            # Load weights (with module prefix stripping)
            state_dict = torch.load(path, map_location=self.device)
            new_state_dict = {}
            for k, v in state_dict.items():
                name = k[7:] if k.startswith('module.') else k
                new_state_dict[name] = v
            
            model.load_state_dict(new_state_dict)
            model.eval()
            
            self.models.append(model)
            self.model_configs.append({
                'scale': scale,
                'width': w_input,
                'height': h_input
            })
            print(f"Loaded Anti-Spoof Model: {model_type} (Scale: {scale})")

    def predict(self, frame, face_box):
        """
        Predict liveness score for a face.
        face_box: [x, y, w, h] (Haar cascade format)
        """
        if not self.models:
            return 0.0
            
        results = []
        for i, model in enumerate(self.models):
            config = self.model_configs[i]
            
            # Use official cropping logic
            # Note: face_box in Haar format is [x, y, w, h], which matches self.cropper expectations
            img_crop = self.cropper.crop(frame, face_box, config['scale'], config['width'], config['height'])
            
            # Preprocess (ToTensor + Normalize is built into the official transform or manual)
            # The official repo just uses transform.ToTensor()
            img_tensor = torch.from_numpy(img_crop.transpose((2, 0, 1))).float()
            img_tensor = img_tensor.unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                result = model(img_tensor)
                result = F.softmax(result, dim=1).cpu().numpy()
                # MiniVision classes: 1 is REAL
                results.append(result[0][1])
                
        # Return average confidence score
        return np.mean(results) if results else 0.0
