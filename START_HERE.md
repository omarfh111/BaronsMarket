# Start Here - BaronsMarket

This file is the quick entry point for running and evaluating the BaronsMarket AI Platform.

## 1. Project Context

BaronsMarket is an academic smart-retail engineering project developed at Esprit School of Engineering. It combines:

- Flutter mobile shopping app
- FastAPI backend
- Employee web dashboard
- Computer vision models
- Multi-agent RAG shopping assistant
- Qdrant semantic search
- Supabase persistence
- CUDA-ready inference for GPU servers

## 2. Main Folders

```text
backend/                     FastAPI backend and AI services
frontend/                    Flutter Android app
apps/web-employee/public/    Employee dashboard served by FastAPI
model/                       Model assets and configuration files
ml/models/                   Model code and trained weights
market/                      Product catalog data
docs/                        Documentation and screenshot notes
```

## 3. First Backend Run

```powershell
cd backend
python -m venv ..\venv
..\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/models/device`
- `http://127.0.0.1:8000/employee/`

## 4. CUDA / GPU Check

Use the same Python environment that starts the backend:

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

The project supports:

```env
MODEL_DEVICE=auto
```

Allowed values:

- `auto`: use CUDA if available, otherwise CPU
- `cuda`: prefer CUDA
- `cpu`: force CPU

## 5. Mobile App Run

```powershell
cd frontend
flutter pub get
flutter run --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

Build APK:

```powershell
flutter build apk --release --dart-define=API_BASE_URL=http://<PC_LOCAL_IP>:8000
```

APK path:

```text
frontend/build/app/outputs/flutter-apk/app-release.apk
```

## 6. Evaluation Flow

Recommended demo order:

1. Open employee dashboard at `/employee/`.
2. Test queue recommendation with a video.
3. Test theft surveillance with a video.
4. Test forged document detection.
5. Test employee access verification.
6. Open the mobile app and scan a product.
7. Test cart and checkout QR.
8. Ask the assistant for a recipe and verify it returns a complete ingredient basket from catalog products.
9. Open analytics dashboard.
10. Show `/models/device` to prove CUDA/GPU readiness.

## 7. Assistant Behavior

The assistant uses multi-agent RAG logic:

- General agent for friendly product search and recommendations.
- Chef agent for recipes and automatic ingredient basket creation.
- Nutrition agents for healthier guidance.
- Support agent for application/help issues.
- Router agent to select the right agent.
- Search translator agent to improve Qdrant/catalog search.

For recipe requests, product cards are ingredients of the recipe basket, not random product recommendations.

## 8. Deployment Notes

Development can run locally. For remote testing, Cloudflare Tunnel can expose the backend temporarily.

Recommended production target:

- GPU server such as Hetzner with CUDA-capable NVIDIA GPU
- Supabase for persistence
- Qdrant for vector search
- FastAPI serving backend and employee dashboard

## 9. Documentation Checklist Before Final Submission

- Add final live demo URL if available.
- Add real screenshots under `docs/screenshots/`.
- Add GitHub topics listed in `README.md` from the repository About panel.
- Verify `.env.example` does not contain secrets.
- Verify `GET /models/device` shows expected GPU status on the deployment machine.
