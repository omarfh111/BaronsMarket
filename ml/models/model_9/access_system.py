import cv2
import numpy as np
import os
from deepface import DeepFace
from dotenv import load_dotenv
from collections import Counter
import face_recognition
import sys
import torch
import easyocr
from scipy.fft import fft2, fftshift
from skimage.feature import local_binary_pattern
from anti_spoof_v2 import AntiSpoofPredictor

# Initialize the new Silent-Face-Anti-Spoofing Engine
predictor = AntiSpoofPredictor()


# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()
SUPERMARKET_NAME = os.getenv("SUPERMARKET_NAME", "Monoprix")

# --- CONFIGURATION ---
# ArcFace Threshold: Cosine distance < 0.68 is usually a match
# Accuracy: High | Weights size: ~140MB
FACE_THRESHOLD_ARC = 0.68   
MATCH_PERCENT_MIN  = 45      # Percentage calculation for ArcFace (User requested > 45%)
PROCESS_EVERY_N_FRAMES = 2    
BUFFER_SIZE = 12             
EAR_THRESHOLD    = 0.18       

def calculate_ear(eye_landmarks):
    p = eye_landmarks
    def dist(p1, p2): return np.linalg.norm(np.array(p1) - np.array(p2))
    v1, v2, h = dist(p[1], p[5]), dist(p[2], p[4]), dist(p[0], p[3])
    return (v1 + v2) / (2.0 * h) if h > 0 else 0

def check_texture_lbp(face_crop):
    """Advanced Texture Analysis using LBP."""
    try:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (100, 100))
        radius = 3
        n_points = 8 * radius
        lbp = local_binary_pattern(gray, n_points, radius, method='uniform')
        (hist, _) = np.histogram(lbp.ravel(), bins=np.arange(0, n_points + 3), range=(0, n_points + 2))
        hist = hist.astype("float")
        hist /= (hist.sum() + 1e-7)
        # Uniform patterns sum
        score = hist[1] + hist[2] + hist[3] 
        return score
    except: return 0

def analyze_face(frame, face_box):
    x, y, w, h = face_box
    margin = 35
    h_max, w_max = frame.shape[:2]
    y1, y2 = max(0, y - margin), min(h_max, y + h + margin)
    x1, x2 = max(0, x - margin), min(w_max, x + w + margin)
    face_crop = frame[y1:y2, x1:x2].copy()
    
    if face_crop.size == 0 or face_crop.shape[0] < 45:
        return False, None, 0, 0

    try:
        texture_score = check_texture_lbp(face_crop)
        
        # New: Specialized MiniVision Engine (Silent-Face-Anti-Spoofing)
        # Using 2.7x and 4.0x scales as per the original engine logic
        liveness_score = predictor.predict(frame, face_box)
        is_live_engine = liveness_score > 0.90 # Adjust threshold if needed
        
        rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        ear = 0
        try:
            face_landmarks_list = face_recognition.face_landmarks(rgb_crop)
            if face_landmarks_list:
                landmarks = face_landmarks_list[0]
                ear = (calculate_ear(landmarks["left_eye"]) + calculate_ear(landmarks["right_eye"])) / 2.0
        except: pass
            
        # Liveness Consensus (Weighted)
        # 1. MiniVision Engine (Primary)
        # 2. LBP Texture (Secondary)
        liveness_weight = 0
        if is_live_engine: liveness_weight += 2 
        if texture_score > 0.12: liveness_weight += 1
        
        is_real = liveness_weight >= 2
        
        # Identity (ARCFACE) - Keep it for recognition
        res = DeepFace.represent(img_path=face_crop, model_name="ArcFace", enforce_detection=False, detector_backend="opencv")
        embedding = res[0]["embedding"] if res else None
        
        return is_real, embedding, ear, liveness_score # Return engine score for UI display
    except Exception as e:
        print(f"Error analyzing face: {e}")
        return False, None, 0, 0

def get_similarity(emb1, emb2):
    if emb1 is None or emb2 is None: return 1.0
    emb1, emb2 = np.array(emb1), np.array(emb2)
    # Cosine distance
    dist = 1 - (np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
    return dist

# --- INITIALIZATION ---
print("\n🔥 SECURE ACCESS SYSTEM V7 (ArcFace Mode)")
print("------------------------------------------")

# Camera Discovery
def get_available_cameras():
    index = 0
    arr = []
    while index < 4: 
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if cap.isOpened():
            arr.append(index)
            cap.release()
        index += 1
    return arr

print("1. Scanning for Cameras...")
cams = get_available_cameras()

# INTERACTIVE SELECTION
camera_index = 0
if len(sys.argv) > 1:
    try: camera_index = int(sys.argv[1])
    except: pass
else:
    print(f"   Available camera indices: {cams}")
    try:
        choice = input(f"   👉 Enter camera index to use (default {cams[0] if cams else 0}): ").strip()
        camera_index = int(choice) if choice else (cams[0] if cams else 0)
    except:
        camera_index = cams[0] if cams else 0

print(f"2. Using Camera Index: {camera_index}")
print("3. Preparing ArcFace Engine (Loading Models)...")

# Warp-up OCR Engine
print("4. Initializing EasyOCR Engine...")
try:
    reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
    print("5. EasyOCR initialized.")
except Exception as e:
    print(f"5. Error initializing EasyOCR: {e}")
    reader = None

# Warm-up call
try:
    dummy = np.zeros((150, 150, 3), dtype=np.uint8)
    DeepFace.represent(img_path=dummy, model_name="ArcFace", enforce_detection=False)
    print("6. ArcFace Model Loaded Successfully.")
except Exception as e:
    print(f"6. Note: ArcFace model is initializing...")

# --- STATE ---
results_history = [] 
blink_state = "OPEN"
last_status = "Waiting..."
last_color  = (200, 200, 200)
ocr_text_found = ""
ocr_status = False
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
last_summary = {"similarity": 0, "real": [], "fake": [], "ocr_ok": False}

# --- WINDOW CONFIGURATION ---
cv2.namedWindow("Secure Face Access", cv2.WINDOW_NORMAL)


cap = cv2.VideoCapture(camera_index)
if not cap.isOpened():
    print(f"❌ Error: Camera {camera_index} not found.")
    sys.exit()

frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret: break
    frame_count += 1

    if frame_count % PROCESS_EVERY_N_FRAMES == 0:
        # Scale for detection (Target ~640px width for speed)
        det_scale = 640.0 / frame.shape[1]
        gray_small = cv2.cvtColor(cv2.resize(frame, (0, 0), fx=det_scale, fy=det_scale), cv2.COLOR_BGR2GRAY)
        detected_faces = face_cascade.detectMultiScale(gray_small, 1.1, 6, minSize=(40, 40))
        
        real_faces, fake_faces = [], []
        for (x, y, w, h) in detected_faces:
            # Map coordinates back to original resolution
            box_full = (int(x / det_scale), int(y / det_scale), int(w / det_scale), int(h / det_scale))
            is_real, embedding, ear, texture = analyze_face(frame, box_full)
            
            face_info = {"box": box_full, "embedding": embedding, "ear": ear, "texture": texture}
            if is_real:
                if blink_state == "OPEN" and ear < EAR_THRESHOLD: blink_state = "CLOSED"
                elif blink_state == "CLOSED" and ear > (EAR_THRESHOLD + 0.05): blink_state = "BLINK_DONE"
                real_faces.append(face_info)
            else:
                fake_faces.append(face_info)

        frame_result = "searching"
        current_similarity = 0

        if len(real_faces) > 0 and len(fake_faces) > 0:
            real, fake = real_faces[0], fake_faces[0]
            dist = get_similarity(real["embedding"], fake["embedding"])
            # Match % for ArcFace (dist 0.68 = ~40%)
            current_similarity = max(0, min(100, (1 - (dist / 1.0)) * 100))
            
            # --- OCR CHECK ON BADGE ---
            ocr_status = False
            ocr_text_found = ""
            if reader:
                # Expand crop to capture badge text around the face
                fx, fy, fw, fh = fake["box"]
                h_max, w_max = frame.shape[:2]
                # Much larger scan area (2x left/up, 3x right/down) to ensure we catch badges of all sizes
                x1 = max(0, fx - 2*fw)
                y1 = max(0, fy - 2*fh)
                x2 = min(w_max, fx + 3*fw)
                y2 = min(h_max, fy + 4*fh)
                badge_crop = frame[y1:y2, x1:x2]
                
                if badge_crop.size > 0:
                    # Small contrast boost to help OCR see text on thin badges
                    badge_crop = cv2.convertScaleAbs(badge_crop, alpha=1.2, beta=10)
                    results = reader.readtext(badge_crop)
                    detected_text = ""
                    ocr_box = None
                    for res in results:
                        txt = res[1].lower()
                        detected_text += txt + " "
                        if SUPERMARKET_NAME.lower() in txt:
                            # Found the specific box for the name
                            box = res[0]
                            ocr_box = [(int(box[0][0] + x1), int(box[0][1] + y1)), 
                                       (int(box[2][0] + x1), int(box[2][1] + y1))]
                    
                    ocr_text_found = detected_text.strip()
                    if SUPERMARKET_NAME.lower() in ocr_text_found:
                        ocr_status = True
            
            # Access Criteria: Threshold ok, Similarity > 45%, and OCR OK
            if dist < FACE_THRESHOLD_ARC and current_similarity >= MATCH_PERCENT_MIN and ocr_status:
                frame_result = "access_granted" if blink_state == "BLINK_DONE" else "verify_liveness"
            elif not ocr_status and len(fake_faces) > 0:
                frame_result = "invalid_badge"
            elif current_similarity < MATCH_PERCENT_MIN:
                frame_result = "faces_dont_match"
            else:
                frame_result = "searching"
                
            if current_similarity < MATCH_PERCENT_MIN:
                blink_state = "OPEN"
        else:
            ocr_box = None
            if len(real_faces) == 0: blink_state = "OPEN"

        results_history.append(frame_result)
        if len(results_history) > BUFFER_SIZE: results_history.pop(0)
        consensus = Counter(results_history).most_common(1)[0][0]

        if consensus == "access_granted":
            last_status, last_color = "ACCESS GRANTED", (0, 255, 0)
        elif consensus == "verify_liveness":
            last_status, last_color = "LIVENESS: PLEASE BLINK", (0, 255, 255)
        elif consensus == "faces_dont_match":
            last_status, last_color = "IDENTITY MISMATCH", (0, 0, 255)
        elif consensus == "invalid_badge":
            last_status, last_color = f"WRONG BADGE: NEED {SUPERMARKET_NAME.upper()}", (0, 0, 255)
        else:
            last_status, last_color = "SHOW FACE AND BADGE", (200, 200, 200)
        
        last_summary = {
            "similarity": current_similarity, 
            "real": real_faces, 
            "fake": fake_faces, 
            "ocr_ok": ocr_status,
            "ocr_box": ocr_box
        }

    # --- RENDERING ---
    # Auto-scale output for display (Target ~1280px width to fit screen)
    disp_w = 1280
    h_orig, w_orig = frame.shape[:2]
    disp_scale = min(1.0, disp_w / w_orig)
    display_frame = cv2.resize(frame, (0, 0), fx=disp_scale, fy=disp_scale)

    for f in last_summary.get("real", []):
        x, y, w, h = [int(v * disp_scale) for v in f["box"]]
        cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(display_frame, f"REAL (L: {f['texture']:.2f})", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    for f in last_summary.get("fake", []):
        x, y, w, h = [int(v * disp_scale) for v in f["box"]]
        cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.putText(display_frame, f"SPOOF (L: {f['texture']:.2f})", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    if last_summary["similarity"] > 0:
        cv2.putText(display_frame, f"ArcFace Match: {last_summary['similarity']:.1f}%", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Show OCR Status
        ocr_color = (0, 255, 0) if last_summary["ocr_ok"] else (0, 0, 255)
        ocr_label = f"BADGE TEXT: {SUPERMARKET_NAME.upper()}" if last_summary["ocr_ok"] else "BADGE TEXT: NOT FOUND"
        cv2.putText(display_frame, ocr_label, (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ocr_color, 2)

        # DRAW OCR BOX ON BADGE
        if last_summary["ocr_box"]:
            p1, p2 = last_summary["ocr_box"]
            p1 = (int(p1[0] * disp_scale), int(p1[1] * disp_scale))
            p2 = (int(p2[0] * disp_scale), int(p2[1] * disp_scale))
            cv2.rectangle(display_frame, p1, p2, (255, 255, 0), 2) # Cyan/Yellow box around text
            cv2.putText(display_frame, "VERIFIED", (p1[0], p1[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # DEBUG: Show what OCR is actually seeing (helps with positioning)
        if ocr_text_found:
            debug_txt = f"OCR SEES: {ocr_text_found[:40]}..." if len(ocr_text_found) > 40 else f"OCR SEES: {ocr_text_found}"
            cv2.putText(display_frame, debug_txt, (20, display_frame.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Top Status Bar
    cv2.rectangle(display_frame, (0, 0), (display_frame.shape[1], 50), (30, 30, 30), -1)
    cv2.putText(display_frame, last_status, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, last_color, 2)
    
    if blink_state == "BLINK_DONE" and consensus != "access_granted":
        msg = "✅ BLINK DETECTED"
        cv2.putText(display_frame, msg, (display_frame.shape[1]-240, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("Secure Face Access", display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()