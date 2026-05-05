# Project Split: Mobile Client + Web Employee

This repository is now organized to separate:

- mobile app for clients
- web app for employees
- shared ML/inference backend

## Current working code (already exists)

- Mobile client app: `frontend/`
- Inference API backend: `backend/`
- Existing model assets: `model/`

## New target structure (prepared)

- `apps/mobile-client/`
- `apps/web-employee/`
- `services/inference-api/`
- `ml/models/model_1/`
- `ml/models/model_2/`
- `ml/notebooks/`
- `data/raw/`, `data/processed/`, `data/exports/`

## Where to put files now

1. Mobile client source code:
- keep using `frontend/` for now
- later move into `apps/mobile-client/`

2. Web employee source code:
- start directly in `apps/web-employee/`
- put pages/components in `apps/web-employee/src/`

3. API backend code:
- keep using `backend/` for now
- later move into `services/inference-api/`

4. Models:
- product detection/retrieval model files -> `ml/models/model_1/`
- meat freshness model files (`best_model_meat_freshness_detection_Efficent_Net.pth`) -> `ml/models/model_2/`

5. Notebooks:
- all training notebooks (`meatfreshness...ipynb`, etc.) -> `ml/notebooks/`

6. Datasets and exports:
- original datasets -> `data/raw/`
- cleaned/transformed datasets -> `data/processed/`
- generated outputs/reports -> `data/exports/`

## Backend config when you move models

In `backend/.env`, set:

- `MODEL_DIR=../ml/models/model_1`
- `YOLO_MODEL_PATH=../ml/models/model_1/best.pt`
- `FAISS_INDEX_PATH=../ml/models/model_1/index.faiss`
- `PRODUCT_EMBEDDINGS_PATH=../ml/models/model_1/product_embeddings_aug.npy`
- `PRODUCTS_JSON_PATH=../ml/models/model_1/products_clean .json`

The meat freshness service already reads from:
- `../model/model_2/...` currently

When you move it to `ml/models/model_2`, update:
- `backend/app/services/meat_freshness_service.py`

