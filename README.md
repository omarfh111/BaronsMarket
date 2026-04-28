# BaronsMarket AI Platform

Unified project for supermarket AI use cases:
- Mobile shopping assistant (product scan, cart, QR checkout)
- Employee web platform (Animal/Bag, Theft surveillance, Queue recommendation)

## Repository Structure

- `backend/`: FastAPI API server (all AI endpoints + employee web static hosting)
- `frontend/`: Flutter Android app for client experience
- `apps/web-employee/public/`: employee web UI
- `model/model_1/`: product detection/retrieval assets
- `model/model_2/`: meat freshness model weights
- `model/model_5/`: queue zones JSON used by backend
- `ml/models/model_3/`: animal/bag model weights
- `ml/models/model_4/`: theft pipeline models
- `ml/models/model_5/`: queue recommendation notebook-aligned config and YOLO weights

## Features Implemented

1. Product scan (mobile)
- YOLOv8 detection + CLIP embedding + FAISS retrieval
- Top predictions with confirm/reject
- Cart and QR checkout

2. Animal & Bag (employee web)
- Image and video analysis
- Bounding boxes, events, thresholds

3. Theft surveillance (employee web)
- Person detection + tracking + theft status decision
- Auto capture when `SUSPECT` or `THEFT`
- Upload video + YouTube mode (environment dependent)

4. Queue recommendation (employee web + mobile)
- Track people in queue zones
- Count per queue and choose best queue
- Async background jobs + live status polling
- Mobile checkout can read latest recommended queue

## System Requirements

### Windows tools

- Python 3.10+ (3.11 recommended)
- Git + Git LFS
- Flutter SDK (tested 3.41.x)
- Android Studio
- Android SDK (platform-tools, build-tools, command-line tools)

### Optional for YouTube direct analysis

- `ffmpeg`
- `yt-dlp`

## Step-by-Step Setup

### 1) Clone and prepare

```powershell
git clone -b integration https://github.com/omarfh111/BaronsMarket.git
cd BaronsMarket
git lfs pull
```

### 2) Backend install

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 3) Start backend

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4) Web employee test

Open:
- `http://127.0.0.1:8000/employee/`

Test tabs:
- Animal & Bag
- Surveillance Vol
- Recommandation Caisse

### 5) Flutter setup

```powershell
cd ..\frontend
flutter pub get
flutter doctor
flutter doctor --android-licenses
```

If flutter is not in PATH:

```powershell
$env:Path += ";C:\src\flutter\bin"
flutter --version
```

### 6) Build APK for real phone

```powershell
flutter build apk --release --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

APK path:
- `frontend/build/app/outputs/flutter-apk/app-release.apk`

### 7) Install and test on phone

- Phone and PC on same Wi-Fi
- Backend must remain running
- Verify backend access from phone browser:
  - `http://<PC_LOCAL_IP>:8000/health`

## Execution Flow (Recommended)

1. Employee uploads surveillance/queue video in web panel.
2. Backend computes latest queue recommendation in background.
3. Customer uses mobile app, scans products, confirms cart.
4. At checkout screen, app displays total + QR + latest recommended queue.

## Environment Notes

- `backend/.env.example` contains model path variables for model1/model3/model4/model5.
- Queue zones can be edited in:
  - `model/model_5/queue_zones.json`
- Notebook-aligned queue config (zones/colors/smoothing):
  - `ml/models/model_5/queue_config.json`

## Troubleshooting

- Build fails on large files in GitHub:
  - ensure Git LFS is installed and tracked files are configured.
- Queue stays `N/A`:
  - check queue zone coordinates match the video perspective.
- YouTube endpoint fails:
  - install `ffmpeg` + `yt-dlp`, verify network and video accessibility.
