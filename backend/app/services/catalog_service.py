from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return (
        text.replace("Â", "")
        .replace("Ã©", "e")
        .replace("Ã¨", "e")
        .replace("Ã¢", "a")
        .replace("Ãª", "e")
        .replace("Ã´", "o")
        .replace("Ã»", "u")
        .replace("Ã", "")
    )


def _parse_price(value: Any) -> float:
    text = _clean_text(value).upper().replace("DT", "").replace("TND", "").strip()
    text = text.replace(",", ".").replace(" ", "")
    try:
        return round(float(text), 3)
    except ValueError:
        return 0.0


class CatalogService:
    def __init__(self) -> None:
        self.catalog_root = _resolve_path(settings.market_catalog_dir)
        self._products: list[dict[str, Any]] = []
        self._categories: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self.catalog_root.exists():
            return

        metadata_files = sorted(self.catalog_root.glob("output_*/products_metadata.json"))
        products: list[dict[str, Any]] = []

        for meta_file in metadata_files:
            category = meta_file.parent.name.replace("output_", "").replace("_", " ").title()
            images_dir = meta_file.parent / "images"
            try:
                raw_items = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(raw_items, list):
                continue

            for item in raw_items:
                image_file = str(item.get("image_file", "")).strip()
                image_path = (images_dir / image_file).resolve() if image_file else None
                if not image_path or not image_path.exists():
                    continue

                products.append(
                    {
                        "id": str(item.get("product_id") or f"{category}-{image_file}"),
                        "name": _clean_text(item.get("name") or "Unknown Product"),
                        "brand": _clean_text(item.get("brand") or "Unknown Brand"),
                        "price": _parse_price(item.get("price")),
                        "category": category,
                        "image_file": image_file,
                        "image_path": str(image_path),
                    }
                )

        self._products = products
        self._categories = sorted({p["category"] for p in products})

    def list_products(
        self,
        page: int = 1,
        page_size: int = 30,
        category: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)

        items = self._products
        if category:
            wanted = category.strip().lower()
            items = [p for p in items if p["category"].lower() == wanted]
        if query:
            q = query.strip().lower()
            items = [p for p in items if q in p["name"].lower() or q in p["brand"].lower()]

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        out = []
        for p in page_items:
            out.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "brand": p["brand"],
                    "price": p["price"],
                    "category": p["category"],
                    "image": f"/catalog/image/{p['id']}",
                }
            )

        return {
            "items": out,
            "total": total,
            "page": page,
            "page_size": page_size,
            "categories": self._categories,
        }

    def get_image_path(self, product_id: str) -> Path | None:
        for p in self._products:
            if p["id"] == product_id:
                return Path(p["image_path"])
        return None

    def all_products(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in self._products:
            out.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "brand": p["brand"],
                    "price": p["price"],
                    "category": p["category"],
                    "image": f"/catalog/image/{p['id']}",
                }
            )
        return out


catalog_service = CatalogService()
