# Market AI - Mobile Shopping Assistant

Full-stack prototype for in-store product scanning and assisted checkout.

## Project Structure

- `backend/`: FastAPI inference API (YOLOv8 + CLIP + FAISS)
- `frontend/`: Flutter mobile app (scan -> predict -> cart -> QR checkout)
- `model/model_1/`: trained assets (`best.pt`, FAISS index, embeddings, products JSON)

## Architecture

1. Mobile app captures image.
2. Backend detects product region with YOLOv8.
3. Crop is embedded with CLIP (512D).
4. Retrieval is performed with FAISS.
5. Backend returns top predictions (`name`, `brand`, `price`, `image`, confidence).
6. User confirms prediction -> product added to local cart.
7. Checkout screen displays total and QR bill payload.

## Prerequisites

### Backend

- Python `3.10+` (recommended `3.11`)
- Pip and virtualenv
- Model files present in `model/model_1/`

### Frontend (Android)

- Flutter SDK (tested with `3.41.x`)
- Android Studio
- Android SDK + build-tools + platform-tools + command-line tools
- Accepted Android licenses (`flutter doctor --android-licenses`)

## Install and Run

### 1) Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

### 2) Frontend setup

```powershell
cd frontend
flutter pub get
```

Run on emulator:

```powershell
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Run on physical phone (same Wi-Fi as backend machine):

```powershell
flutter run --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

Build APK:

```powershell
flutter build apk --release --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

APK output:

- `frontend/build/app/outputs/flutter-apk/app-release.apk`

## Notes

- Android manifest already enables HTTP cleartext for local testing.
- The product metadata filename currently contains a space: `products_clean .json`.
- Some first-time builds are slow because Gradle downloads SDK components.

## Troubleshooting

- `flutter not recognized`: add `C:\src\flutter\bin` to `PATH`.
- Android toolchain missing: run `flutter doctor`, install SDK components in Android Studio.
- Build download timeout: rerun `flutter build apk ...` (Gradle retries often succeed).
- API returns `Only image uploads are supported`: ensure frontend build includes latest API upload fix.
