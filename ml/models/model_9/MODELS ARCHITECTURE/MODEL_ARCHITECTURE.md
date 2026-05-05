# Secure Face Access System - Model Architectures

This document explains the underlying architecture of each Artificial Intelligence and Computer Vision model utilized in the pipeline of the **Secure Face Access System**.

---

## 1. Face Recognition: ArcFace & VGG-Face (via DeepFace)
**Purpose**: Extract robust facial embeddings to identify and verify the employee.

- **ArcFace (Primary verifier in `access_system.py`)**:
  - **Architecture**: A deep Convolutional Neural Network (often based on ResNet architectures like ResNet-50 or ResNet-100).
  - **Loss Function**: It uses an Additive Angular Margin Loss. Instead of standard Softmax, ArcFace projects the deep features onto a hypersphere and adds an angular penalty margin between classes.
  - **Why it works**: This forces the network to maximize inter-class distance (making different people look very different) while minimizing intra-class distance (ensuring photos of the same person group tightly together), outputting a highly discriminative 512-dimensional embedding vector.
  
- **VGG-Face (Configured in `encode_employees.py`)**:
  - **Architecture**: Based on the VGG-16 network. It consists of blocks of 3x3 convolutional layers followed by max-pooling, ending in fully connected layers.

---

## 2. Liveness Detection & Anti-Spoofing: MiniFASNet (Silent-Face-Anti-Spoofing)
**Purpose**: Differentiate a live 3D face from a 2D spoof attempt (printed photo, digital screen, or mask).

- **Architecture**:
  - Integrates lightweight CNNs known as **MiniFASNet** (specifically `MiniFASNetV1SE` and `MiniFASNetV2`), designed for high-spe*ed edge inference.
  - **Multi-Scale Input Context**: The models take inputs at different scales (e.g., 2.7x and 4.0x the bounding box size). This allows the network to learn both the facial micro-textures and the surrounding context (such as detecting the bezel of a phone or the edge of a piece of paper).
  - **Squeeze-and-Excitation (SE) Networks**: Uses SE blocks to perform channel-wise feature re-calibration. It learns to emphasize the most important feature channels for detecting spoofing artifacts (like moiré patterns from screens or reflections) and suppress unhelpful ones.

---

## 3. Optical Character Recognition (OCR): EasyOCR
**Purpose**: Scan the employee badge and extract text to verify the supermarket/company name.

EasyOCR operates using a two-stage deep learning pipeline:
- **Text Detection (CRAFT)**: Character Region Awareness for Text Detection. It uses a VGG-16-based fully convolutional network architecture to predict character region probabilities and the geometric affinities between characters, grouping them into bounding boxes for words.
- **Text Recognition (CRNN)**: A Convolutional Recurrent Neural Network.
  - **Feature Extraction**: Uses a ResNet to extract features from the cropped text boxes.
  - **Sequence Modeling**: Employs Bi-directional LSTMs to capture the sequential context of characters.
  - **Decoding**: Uses CTC (Connectionist Temporal Classification) to decode the raw RNN output into a readable text string without needing perfectly aligned labeled data.

---

## 4. Secondary Texture Analysis: LBP (Local Binary Patterns)
**Purpose**: An additional, lightweight texture analysis layer to supplement the deep learning liveness model.

- **Algorithm Mechanics**: LBP is a classic computer vision algorithm. It iterates over a 100x100 grayscale crop of the face and compares the intensity of the center pixel to its circular neighborhood (e.g., radius of 3, 24 surrounding points).
- **Output**: Generates a histogram of "uniform patterns" (binary transitions).
- **Why it works**: Real human skin scatters light and has a different micro-texture histogram than a flat OLED screen or a printed sheet of A4 paper.

---

## 5. Blink Detection (Challenge-Response Liveness)
**Purpose**: Forces the user to perform a blink to prove they are physically present, combatting static photo spoofs.

- **Architecture**:
  - Employs the `face_recognition` library, which is built on **Dlib’s Ensemble of Regression Trees (ERT)**.
  - **ERT**: A highly efficient machine learning model that estimates 68 specific facial landmark coordinates (points around the chin, eyes, nose, and mouth) in real-time.
  - **Logic (EAR - Eye Aspect Ratio)**: Calculates the ratio of the vertical distance between the eyelids to the horizontal distance of the eye. A sudden, sharp drop and rise in this ratio indicates a legitimate blink.

---

## 6. Fast Face Detection: Haar Cascades
**Purpose**: Acts as the initial lightweight trigger for the entire system, rapidly locating regions of interest in a video frame.

- **Architecture**:
  - Uses OpenCV’s `haarcascade_frontalface_default.xml`.
  - An AdaBoost-based machine learning approach that slides fixed-size windows over the image to calculate "Haar-like features" (subtracting the sum of pixels in white rectangles from black rectangles).
  - **Cascaded Structure**: Designed to reject regions without faces extremely quickly in the early stages, only passing difficult regions to the deeper nodes of the tree, allowing for lightweight processing before the heavier Deep Neural Networks take over.
