"""
DTD DocTamper Inference Module
Simplified for Gradio deployment on Hugging Face
Uses scipy DCT as alternative to jpegio (which has compilation issues)
"""
import os
import sys
import cv2
import torch
import numpy as np
import pickle
import tempfile
from PIL import Image
from scipy.fftpack import dct
import torchvision.transforms as transforms
try:
    import jpegio as jio  # type: ignore
except Exception:
    jio = None

# Force-disable native jpegio path on Windows due to intermittent libjpeg
# runtime crashes ("Improper call to JPEG library in state 201").
jio = None

# Add models directory to path to avoid circular imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'models'))

# Import compatibility fixes and model
import fix_imports
import patch_gelu
import patch_droppath
from dtd import seg_dtd

class DTDPredictor:
    def __init__(self, checkpoint_path='checkpoints/dtd_doctamper.pth', device='cpu'):
        """
        Initialize DTD model for inference

        Args:
            checkpoint_path: Path to model checkpoint
            device: Device to use ('cpu', 'cuda', or 'auto')
        """
        # Auto-detect device
        if device == 'auto':
            if torch.cuda.is_available():
                self.device = 'cuda'
            else:
                self.device = 'cpu'
        else:
            self.device = device

        print(f'Using device: {self.device}')

        # Load QT table
        with open('checkpoints/qt_table.pk', 'rb') as fpk:
            pks = pickle.load(fpk)
        self.pks = {}
        for k, v in pks.items():
            self.pks[k] = torch.LongTensor(v)

        # Image transforms
        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.455, 0.406),
                               std=(0.229, 0.224, 0.225))
        ])

        # Load model
        self.model = seg_dtd('', 2, device=self.device)
        if self.device == 'cuda':
            self.model = self.model.cuda()
        self.model = self.model.to(self.device)

        # Load checkpoint
        ckpt = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
        state_dict = ckpt['state_dict']

        # Remove 'module.' prefix if present
        new_state_dict = {}
        for k, v in state_dict.items():
            if k.startswith('module.'):
                new_state_dict[k[7:]] = v
            else:
                new_state_dict[k] = v

        self.model.load_state_dict(new_state_dict)
        self.model.eval()

        print('Model loaded successfully!')

    def extract_dct(self, image_array, quality=90):
        """
        Extract DCT coefficients using scipy (alternative to jpegio)
        Uses Y channel from YCbCr like actual JPEG compression

        NOTE: This extracts UNQUANTIZED DCT from raw image data,
        which differs from jpegio that reads quantized DCT from JPEG files.
        The model was trained on quantized coefficients, so results may vary.

        Args:
            image_array: RGB image as numpy array (must be 8x8 aligned)
            quality: JPEG quality (used for QT approximation)

        Returns:
            DCT coefficients and quantization table
        """
        # Convert RGB to YCbCr and extract Y channel (luminance)
        # This matches what JPEG compression does
        im_ycbcr = cv2.cvtColor(image_array, cv2.COLOR_RGB2YCrCb)
        y_channel = im_ycbcr[:, :, 0].astype(np.float32) - 128  # Center around 0

        # Image should already be 8x8 aligned
        h, w = y_channel.shape
        assert h % 8 == 0 and w % 8 == 0, f"Image must be 8x8 aligned, got {h}x{w}"

        # Compute DCT for each 8x8 block
        dct_coeffs = np.zeros((h, w), dtype=np.float32)
        for i in range(0, h, 8):
            for j in range(0, w, 8):
                block = y_channel[i:i+8, j:j+8]
                dct_block = dct(dct(block.T, norm='ortho').T, norm='ortho')
                dct_coeffs[i:i+8, j:j+8] = dct_block

        # Generate standard JPEG quantization table for given quality
        qt = self.jpeg_quantization_table(quality)

        return dct_coeffs, qt

    def extract_dct_from_jpeg_path(self, image_path):
        """
        Extract quantized DCT coefficients and quantization table directly from JPEG.
        Returns (dct_coeffs, qt_flat) or None if unavailable/fails.
        """
        if jio is None:
            return None
        try:
            jpeg = jio.read(image_path)
            if not getattr(jpeg, "coef_arrays", None):
                return None
            dct = np.array(jpeg.coef_arrays[0], dtype=np.float32)
            qtables = getattr(jpeg, "quant_tables", None)
            if qtables is None or len(qtables) == 0:
                return None
            qt = np.array(qtables[0], dtype=np.int64).reshape(-1)
            if qt.size < 64:
                return None
            return dct, qt[:64]
        except Exception:
            return None

    def jpeg_quantization_table(self, quality):
        """
        Generate standard JPEG quantization table for given quality

        Args:
            quality: JPEG quality (1-100)

        Returns:
            Flattened quantization table (64 values)
        """
        # Standard JPEG luminance quantization table (quality 50)
        base_table = np.array([
            16, 11, 10, 16, 24, 40, 51, 61,
            12, 12, 14, 19, 26, 58, 60, 55,
            14, 13, 16, 24, 40, 57, 69, 56,
            14, 17, 22, 29, 51, 87, 80, 62,
            18, 22, 37, 56, 68, 109, 103, 77,
            24, 35, 55, 64, 81, 104, 113, 92,
            49, 64, 78, 87, 103, 121, 120, 101,
            72, 92, 95, 98, 112, 100, 103, 99
        ])

        # Scale based on quality
        if quality < 50:
            scale = 5000 / quality
        else:
            scale = 200 - 2 * quality

        qt = np.floor((base_table * scale + 50) / 100)
        qt = np.clip(qt, 1, 255)

        return qt.astype(int)

    def crop_image(self, img, dct, crop_size=512):
        """
        Crop image and DCT into 512x512 patches WITHOUT resize
        Preserves Block Artifact Grids (BAGs)
        """
        h, w = img.shape[:2]
        h_grids = h // crop_size
        w_grids = w // crop_size

        crops = []
        positions = []

        # Regular grid
        for h_idx in range(h_grids):
            for w_idx in range(w_grids):
                y1 = h_idx * crop_size
                x1 = w_idx * crop_size
                y2 = y1 + crop_size
                x2 = x1 + crop_size

                crops.append({
                    'img': img[y1:y2, x1:x2],
                    'dct': dct[y1:y2, x1:x2]
                })
                positions.append((y1, x1, y2, x2))

        # Right edge (overlapping)
        if w % crop_size != 0:
            for h_idx in range(h_grids):
                y1 = h_idx * crop_size
                y2 = y1 + crop_size
                x1 = w - crop_size
                x2 = w

                crops.append({
                    'img': img[y1:y2, x1:x2],
                    'dct': dct[y1:y2, x1:x2]
                })
                positions.append((y1, x1, y2, x2))

        # Bottom edge (overlapping)
        if h % crop_size != 0:
            for w_idx in range(w_grids):
                x1 = w_idx * crop_size
                x2 = x1 + crop_size
                y1 = h - crop_size
                y2 = h

                crops.append({
                    'img': img[y1:y2, x1:x2],
                    'dct': dct[y1:y2, x1:x2]
                })
                positions.append((y1, x1, y2, x2))

        # Bottom-right corner (overlapping)
        if w % crop_size != 0 and h % crop_size != 0:
            crops.append({
                'img': img[h-crop_size:h, w-crop_size:w],
                'dct': dct[h-crop_size:h, w-crop_size:w]
            })
            positions.append((h-crop_size, w-crop_size, h, w))

        return crops, positions, h_grids, w_grids

    @torch.no_grad()
    def predict(self, image_path, quality=90, forged_class_idx=1, use_native_jpeg_dct=True):
        """
        Predict tampering mask for input image
        Uses patch-based processing WITHOUT resize to preserve BAGs

        Args:
            image_path: Path to input JPEG image
            quality: JPEG quality for DCT extraction

        Returns:
            Dictionary containing:
                - original: Original image (numpy array)
                - mask: Binary tampering mask (numpy array)
                - heatmap: Colorized heatmap overlay
        """
        # Load original image and save original dimensions
        im_orig = Image.open(image_path).convert('RGB')
        im_orig_np = np.array(im_orig)
        true_orig_h, true_orig_w = im_orig_np.shape[:2]

        # Align to 8x8 grid to preserve JPEG block structure
        h_aligned = (true_orig_h // 8) * 8
        w_aligned = (true_orig_w // 8) * 8

        # Pad if too small (for processing only)
        img_to_process = im_orig_np.copy()
        if h_aligned < 512 or w_aligned < 512:
            pad_h = max(512 - h_aligned, 0)
            pad_w = max(512 - w_aligned, 0)
            img_to_process = np.pad(img_to_process, ((0, pad_h), (0, pad_w), (0, 0)),
                                    'constant', constant_values=255)
            h_aligned = (img_to_process.shape[0] // 8) * 8
            w_aligned = (img_to_process.shape[1] // 8) * 8

        img_aligned = img_to_process[:h_aligned, :w_aligned]

        # Prefer native JPEG DCT extraction when available; fallback to scipy DCT.
        dct_backend = "scipy_fallback"
        native = self.extract_dct_from_jpeg_path(image_path) if use_native_jpeg_dct else None
        if native is not None:
            dct_native, qt_native = native
            h_native = (int(dct_native.shape[0]) // 8) * 8
            w_native = (int(dct_native.shape[1]) // 8) * 8
            if h_native >= 8 and w_native >= 8:
                # Keep native JPEG DCT and pad/crop to match the RGB branch size.
                dct = np.zeros((h_aligned, w_aligned), dtype=np.float32)
                h_copy = min(h_aligned, h_native)
                w_copy = min(w_aligned, w_native)
                dct[:h_copy, :w_copy] = dct_native[:h_copy, :w_copy]
                qt = qt_native
                dct_backend = "jpegio_padded"
            else:
                dct, qt = self.extract_dct(img_aligned, quality)
                dct_backend = "scipy_fallback_size_mismatch"
        else:
            dct, qt = self.extract_dct(img_aligned, quality)

        # Ensure dimensions match exactly with image-aligned canvas.
        dct_aligned = dct[:h_aligned, :w_aligned]

        # Crop into 512x512 patches
        crops, positions, h_grids, w_grids = self.crop_image(img_aligned, dct_aligned)

        # Process each patch
        full_mask = np.zeros((h_aligned, w_aligned), dtype=np.float32)
        full_class0 = np.zeros((h_aligned, w_aligned), dtype=np.float32)
        full_class1 = np.zeros((h_aligned, w_aligned), dtype=np.float32)
        count_map = np.zeros((h_aligned, w_aligned), dtype=np.int32)

        for crop, (y1, x1, y2, x2) in zip(crops, positions):
            # Prepare inputs
            img_pil = Image.fromarray(crop['img'])
            img_tensor = self.transform(img_pil).unsqueeze(0).to(self.device)

            dct_tensor = torch.from_numpy(
                np.clip(np.abs(crop['dct']), 0, 20).astype(np.int64)
            ).unsqueeze(0).long().to(self.device)

            qt_flat = qt.flatten()[:64]
            qt_tensor = torch.LongTensor(qt_flat).unsqueeze(0).to(self.device)
            qt_tensor = qt_tensor.reshape(1, 1, 8, 8)

            # Forward pass
            output = self.model(img_tensor, dct_tensor, qt_tensor)

            # Use probability map for class "forged" (index 1) instead of argmax.
            # Argmax collapses uncertainty too early and can yield all-black masks.
            probs = torch.softmax(output, dim=1)
            class0_prob = probs[:, 0, :, :].squeeze().cpu().numpy()
            class1_prob = probs[:, 1, :, :].squeeze().cpu().numpy()
            forged_prob = class1_prob if int(forged_class_idx) == 1 else class0_prob

            # Accumulate probability predictions (averaging overlapping regions)
            full_mask[y1:y2, x1:x2] += forged_prob
            full_class0[y1:y2, x1:x2] += class0_prob
            full_class1[y1:y2, x1:x2] += class1_prob
            count_map[y1:y2, x1:x2] += 1

        # Average overlapping regions
        full_mask = full_mask / np.maximum(count_map, 1)
        forgery_score = float(full_mask.mean())

        full_class0 = full_class0 / np.maximum(count_map, 1)
        full_class1 = full_class1 / np.maximum(count_map, 1)

        # Notebook behavior: binary mask at 0.5.
        final_mask = (full_mask > 0.5).astype(np.uint8)

        # Pad mask back to true original size if it was 8x8 aligned smaller
        if final_mask.shape[0] < true_orig_h or final_mask.shape[1] < true_orig_w:
            padded_mask = np.zeros((true_orig_h, true_orig_w), dtype=np.uint8)
            padded_mask[:final_mask.shape[0], :final_mask.shape[1]] = final_mask
            final_mask = padded_mask
        else:
            # Crop if somehow larger (shouldn't happen)
            final_mask = final_mask[:true_orig_h, :true_orig_w]

        # Create heatmap overlay with original image (no padding)
        heatmap = self.create_heatmap(im_orig_np, final_mask)

        return {
            'original': im_orig_np,
            'mask': (final_mask * 255).astype(np.uint8),
            'heatmap': heatmap,
            'forgery_score': forgery_score,
            'class0_score': float(np.mean(full_class0)),
            'class1_score': float(np.mean(full_class1)),
            'dct_backend': dct_backend,
        }

    def create_heatmap(self, image, mask):
        """
        Create colorized heatmap overlay

        Args:
            image: Original image (numpy array)
            mask: Binary mask (numpy array)

        Returns:
            Heatmap overlay (numpy array)
        """
        # Create colored mask
        colored_mask = np.zeros_like(image)
        colored_mask[mask == 1] = [255, 0, 0]  # Red for tampered regions

        # Blend with original image
        alpha = 0.5
        heatmap = cv2.addWeighted(image, 1 - alpha, colored_mask, alpha, 0)

        return heatmap
