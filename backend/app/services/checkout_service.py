from __future__ import annotations

import json
import time
from pathlib import Path
from urllib import error, request

from app.core.config import settings


class CheckoutRepository:
    def __init__(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        self.local_store = backend_root / "outputs" / "checkout_sessions.jsonl"
        self.local_store.parent.mkdir(parents=True, exist_ok=True)

    def _to_record(self, payload: dict) -> dict:
        now_ms = int(time.time() * 1000)
        created_at = payload.get("created_at_unix_ms")
        duration_seconds = None
        if isinstance(created_at, int) and created_at > 0:
            duration_seconds = max(0, int((now_ms - created_at) / 1000))

        cart_id = payload.get("cart_id") or f"cart_{now_ms}"
        return {
            "cart_id": cart_id,
            "recommended_queue": payload["recommended_queue"],
            "total_price": float(payload["total_price"]),
            "items": payload.get("items", []),
            "created_at_unix_ms": created_at,
            "checkout_at_unix_ms": now_ms,
            "duration_seconds": duration_seconds,
            "metadata": payload.get("metadata", {}),
        }

    def _save_local(self, record: dict) -> None:
        with self.local_store.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _save_supabase(self, record: dict) -> None:
        if not settings.supabase_url.strip() or not settings.supabase_service_role_key.strip():
            raise RuntimeError("Supabase non configure")

        base = settings.supabase_url.rstrip("/")
        table = settings.supabase_checkout_table.strip()
        if not table:
            raise RuntimeError("SUPABASE_CHECKOUT_TABLE vide")

        req = request.Request(
            url=f"{base}/rest/v1/{table}",
            method="POST",
            data=json.dumps(record).encode("utf-8"),
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        with request.urlopen(req, timeout=20):
            return

    def save_checkout(self, payload: dict) -> dict:
        record = self._to_record(payload)
        stored_in = "local_jsonl"
        try:
            self._save_supabase(record)
            stored_in = "supabase"
        except Exception:
            self._save_local(record)

        return {
            "cart_id": record["cart_id"],
            "recommended_queue": record["recommended_queue"],
            "total_price": record["total_price"],
            "checkout_at_unix_ms": record["checkout_at_unix_ms"],
            "duration_seconds": record["duration_seconds"],
            "stored_in": stored_in,
        }


class IntegrationsHealthService:
    @staticmethod
    def _is_url(value: str) -> bool:
        return value.startswith("http://") or value.startswith("https://")

    def check(self) -> dict:
        openai_configured = bool(settings.openai_api_key.strip())
        supabase_configured = bool(settings.supabase_url.strip() and settings.supabase_service_role_key.strip())
        qdrant_configured = bool(settings.qdrant_url.strip())

        return {
            "openai": {
                "configured": openai_configured,
                "ok": openai_configured and self._is_url(settings.openai_base_url),
                "details": "ready" if openai_configured else "OPENAI_API_KEY missing",
            },
            "supabase": {
                "configured": supabase_configured,
                "ok": supabase_configured and self._is_url(settings.supabase_url),
                "details": "ready" if supabase_configured else "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing",
            },
            "qdrant": {
                "configured": qdrant_configured,
                "ok": qdrant_configured and self._is_url(settings.qdrant_url),
                "details": "ready" if qdrant_configured else "QDRANT_URL missing",
            },
        }


checkout_repository = CheckoutRepository()
integrations_health_service = IntegrationsHealthService()
