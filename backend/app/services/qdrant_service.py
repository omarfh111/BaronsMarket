from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from app.core.config import settings
from app.services.catalog_service import catalog_service


class QdrantService:
    def _http(self, method: str, url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        req_headers = {"Content-Type": "application/json"}
        if settings.qdrant_api_key.strip():
            req_headers["api-key"] = settings.qdrant_api_key
        if headers:
            req_headers.update(headers)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(url=url, method=method, data=data, headers=req_headers)
        with request.urlopen(req, timeout=40) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}

    def _embed(self, text: str) -> list[float]:
        req = request.Request(
            url=f"{settings.openai_base_url.rstrip('/')}/embeddings",
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "model": settings.openai_embedding_model,
                    "input": text,
                }
            ).encode("utf-8"),
        )
        with request.urlopen(req, timeout=40) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["data"][0]["embedding"]

    def ensure_collection(self, vector_size: int) -> None:
        base = settings.qdrant_url.rstrip("/")
        name = settings.qdrant_collection_name
        try:
            self._http("GET", f"{base}/collections/{name}")
            return
        except Exception:
            pass
        self._http(
            "PUT",
            f"{base}/collections/{name}",
            payload={"vectors": {"size": vector_size, "distance": "Cosine"}},
        )

    def ingest_catalog(self, limit: int = 2000) -> dict[str, Any]:
        if not settings.qdrant_url.strip():
            return {"status": "error", "message": "QDRANT_URL missing"}
        if not settings.openai_api_key.strip():
            return {"status": "error", "message": "OPENAI_API_KEY missing for embeddings"}

        all_items = catalog_service.all_products()
        items = all_items[: min(max(limit, 1), len(all_items))]
        if not items:
            return {"status": "error", "message": "No catalog items found"}

        first_vec = self._embed(f"{items[0]['name']} {items[0]['brand']} {items[0]['category']}")
        self.ensure_collection(len(first_vec))

        points = []
        for idx, item in enumerate(items, start=1):
            text = f"{item.get('name','')} {item.get('brand','')} {item.get('category','')}"
            vec = self._embed(text)
            points.append(
                {
                    "id": idx,
                    "vector": vec,
                    "payload": item,
                }
            )

        base = settings.qdrant_url.rstrip("/")
        name = settings.qdrant_collection_name
        self._http("PUT", f"{base}/collections/{name}/points", payload={"points": points})
        return {"status": "ok", "collection": name, "points": len(points)}

    def search_products(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not settings.qdrant_url.strip() or not settings.openai_api_key.strip():
            return []
        try:
            vec = self._embed(query)
            base = settings.qdrant_url.rstrip("/")
            name = settings.qdrant_collection_name
            body = self._http(
                "POST",
                f"{base}/collections/{name}/points/search",
                payload={"vector": vec, "limit": max(1, min(top_k, 10)), "with_payload": True},
            )
            results = body.get("result", [])
            out = []
            for r in results:
                payload = r.get("payload") or {}
                if payload:
                    out.append(payload)
            return out
        except error.HTTPError:
            return []
        except Exception:
            return []


qdrant_service = QdrantService()
