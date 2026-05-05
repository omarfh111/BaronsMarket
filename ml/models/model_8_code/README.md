---
title: DTD Document Tampering Detection
emoji: 🔍
colorFrom: blue
colorTo: red
sdk: gradio
sdk_version: 5.25.2
app_file: app.py
pinned: false
license: mit
---

# 🔍 DTD: Document Tampering Detection

Detect forged or tampered regions in document images using the **DTD (Document Tampering Detector)** model.

## 📝 Description

This application uses state-of-the-art deep learning to identify manipulated text in document images by analyzing JPEG compression artifacts (DCT coefficients).

### ✨ Features

- **DCT Analysis**: Examines JPEG compression patterns to detect inconsistencies
- **Real-time Detection**: Fast inference on CPU or GPU
- **Visual Heatmaps**: Clear visualization of tampered regions
- **High Accuracy**: Trained on DocTamper dataset with 120K+ document images

### 🎯 Use Cases

- Verify document authenticity
- Detect forged receipts, invoices, and forms
- Identify copy-paste text manipulation
- Detect splicing and content insertion

## 🚀 How It Works

1. **Upload** a document image (JPEG format works best)
2. **Adjust** JPEG quality setting for DCT analysis (default: 90)
3. **View** tampering detection results:
   - **Heatmap**: Red overlay shows tampered regions
   - **Binary Mask**: Clear segmentation of authentic vs tampered
   - **Original**: Compare with input

## 🏗️ Model Architecture

- **Backbone**: VPH (Vision Pyramid Hybrid) + Swin Transformer
- **Decoder**: Multi-scale Iterative Decoder (MID)
- **Inputs**: RGB image + DCT coefficients + Quantization tables
- **Output**: Binary segmentation mask (0=authentic, 1=tampered)

## 📚 Citation

```bibtex
@inproceedings{qu2023towards,
  title={Towards Robust Tampered Text Detection in Document Image: New Dataset and New Solution},
  author={Qu, Chenfan and Liu, Chongyu and Liu, Yuliang and Chen, Xinhong and Peng, Dezhi and Guo, Fengjun and Jin, Lianwen},
  booktitle={Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition},
  pages={5937--5946},
  year={2023}
}
```

## 📖 Paper

[Towards Robust Tampered Text Detection in Document Image: New Dataset and New Solution](https://openaccess.thecvf.com/content/CVPR2023/papers/Qu_Towards_Robust_Tampered_Text_Detection_in_Document_Image_New_Dataset_CVPR_2023_paper.pdf) (CVPR 2023)

## ⚠️ Limitations

- **JPEG Dependency**: Requires JPEG format for DCT analysis
- **Quality Sensitivity**: Detection accuracy varies with compression quality
- **False Positives**: May occur on low-quality scans or heavily compressed images
- **Preprocessing**: Images must contain text/document content

## 🛠️ Technical Details

### Model Weights

- **Main Model**: `dtd_doctamper.pth` (257MB)
- **VPH Backbone**: `vph_imagenet.pt` (4.8MB)
- **Swin Transformer**: `swin_imagenet.pt` (187MB)
- **Total Size**: ~449MB

### Performance

- **Input Size**: Variable (auto-resized)
- **Inference Time**: ~2-5 seconds on CPU
- **GPU Acceleration**: Supported (CUDA)

## 📦 Local Installation

```bash
# Clone repository
git clone https://huggingface.co/spaces/YOUR_USERNAME/dtd-doctamper-detection
cd dtd-doctamper-detection

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Acknowledgments

- Original DTD model by Qu et al. (CVPR 2023)
- DocTamper dataset
- Hugging Face Spaces for hosting
