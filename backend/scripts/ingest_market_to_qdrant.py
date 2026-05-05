from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib import request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.catalog_service import catalog_service  # noqa: E402


def _http_json(method: str, url: str, payload: dict[str, Any] | None, headers: dict[str, str]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(url=url, method=method, data=data, headers=headers)
    with request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def embed_texts(texts: list[str]) -> list[list[float]]:
    body = {
        "model": settings.openai_embedding_model,
        "input": texts,
    }
    out = _http_json(
        "POST",
        f"{settings.openai_base_url.rstrip('/')}/embeddings",
        body,
        {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
    )
    rows = out.get("data", [])
    rows = sorted(rows, key=lambda x: x.get("index", 0))
    return [r["embedding"] for r in rows]


def embed_texts_with_retry(texts: list[str], max_retries: int = 5) -> list[list[float]]:
    attempt = 0
    while True:
        try:
            return embed_texts(texts)
        except Exception as exc:
            attempt += 1
            if attempt > max_retries:
                # If a large batch keeps failing, split to reduce payload size.
                if len(texts) > 1:
                    mid = len(texts) // 2
                    left = embed_texts_with_retry(texts[:mid], max_retries=max_retries)
                    right = embed_texts_with_retry(texts[mid:], max_retries=max_retries)
                    return left + right
                raise RuntimeError(f"Embedding failed after retries: {exc}") from exc
            sleep_s = min(20, 2 * attempt)
            print(f"Embedding retry {attempt}/{max_retries} in {sleep_s}s بسبب: {exc}")
            time.sleep(sleep_s)


def ensure_collection(collection: str, vector_size: int) -> None:
    base = settings.qdrant_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key.strip():
        headers["api-key"] = settings.qdrant_api_key

    try:
        _http_json("GET", f"{base}/collections/{collection}", None, headers)
        return
    except Exception:
        pass

    _http_json(
        "PUT",
        f"{base}/collections/{collection}",
        {"vectors": {"size": vector_size, "distance": "Cosine"}},
        headers,
    )


def upsert_points(collection: str, points: list[dict[str, Any]]) -> None:
    base = settings.qdrant_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.qdrant_api_key.strip():
        headers["api-key"] = settings.qdrant_api_key
    _http_json("PUT", f"{base}/collections/{collection}/points", {"points": points}, headers)


def build_text(product: dict[str, Any]) -> str:
    return (
        f"name: {product.get('name', '')}; "
        f"brand: {product.get('brand', '')}; "
        f"category: {product.get('category', '')}; "
        f"price_tnd: {product.get('price', 0)}"
    )


def _load_resume_index(resume_file: Path) -> int:
    if not resume_file.exists():
        return 0
    try:
        data = json.loads(resume_file.read_text(encoding="utf-8"))
        return int(data.get("next_index", 0))
    except Exception:
        return 0


def _save_resume_index(resume_file: Path, next_index: int, total: int) -> None:
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text(
        json.dumps({"next_index": next_index, "total": total}, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def run(limit: int, batch_size: int, collection: str, dry_run: bool, resume_file: Path, max_retries: int) -> None:
    products = catalog_service.all_products()
    if not products:
        print("Aucun produit trouve dans le dossier market.")
        return

    products = products[: min(limit, len(products))]
    categories = Counter(str(p.get("category", "Unknown")) for p in products)

    print(f"Produits charges: {len(products)}")
    print(f"Categories detectees: {len(categories)}")
    print("Top categories:")
    for name, count in categories.most_common(10):
        print(f"- {name}: {count}")

    if dry_run:
        print("Mode dry-run: aucune ingestion envoyee a Qdrant.")
        return

    if not settings.openai_api_key.strip():
        raise RuntimeError("OPENAI_API_KEY manquant dans backend/.env")
    if not settings.qdrant_url.strip():
        raise RuntimeError("QDRANT_URL manquant dans backend/.env")

    first_vec = embed_texts([build_text(products[0])])[0]
    ensure_collection(collection, len(first_vec))

    total = len(products)
    start_index = _load_resume_index(resume_file)
    if start_index >= total:
        print("Resume index >= total, rien a faire.")
        return

    processed = start_index
    point_id = start_index + 1

    if start_index > 0:
        print(f"Reprise depuis index {start_index}/{total}")

    for i in range(start_index, total, batch_size):
        chunk = products[i : i + batch_size]
        texts = [build_text(p) for p in chunk]
        vectors = embed_texts_with_retry(texts, max_retries=max_retries)

        points = []
        for p, vec in zip(chunk, vectors):
            points.append(
                {
                    "id": point_id,
                    "vector": vec,
                    "payload": p,
                }
            )
            point_id += 1

        upsert_points(collection, points)
        processed += len(chunk)
        pct = math.floor((processed / total) * 100)
        print(f"[{processed}/{total}] {pct}%")
        _save_resume_index(resume_file, processed, total)

    print(f"Ingestion terminee dans la collection '{collection}' avec {processed} produits.")
    _save_resume_index(resume_file, total, total)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion offline de market vers Qdrant")
    parser.add_argument("--limit", type=int, default=2000, help="Nombre max de produits a ingester")
    parser.add_argument("--batch-size", type=int, default=50, help="Taille de batch embeddings/upsert")
    parser.add_argument(
        "--collection",
        type=str,
        default=settings.qdrant_collection_name,
        help="Nom de la collection Qdrant",
    )
    parser.add_argument(
        "--resume-file",
        type=str,
        default=str(BACKEND_DIR / "outputs" / "qdrant_ingest_progress.json"),
        help="Fichier de reprise de progression",
    )
    parser.add_argument("--max-retries", type=int, default=5, help="Nombre de retries par batch embeddings")
    parser.add_argument("--dry-run", action="store_true", help="Analyse seulement, sans ingestion")
    args = parser.parse_args()

    run(
        limit=max(1, args.limit),
        batch_size=max(1, args.batch_size),
        collection=args.collection,
        dry_run=args.dry_run,
        resume_file=Path(args.resume_file),
        max_retries=max(1, args.max_retries),
    )


if __name__ == "__main__":
    main()
