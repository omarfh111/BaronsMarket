from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import parse, request

from app.core.config import settings
from app.services.qdrant_service import qdrant_service


class StoreAnalyticsService:
    def __init__(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        self.local_store = backend_root / "outputs" / "checkout_sessions.jsonl"

    @staticmethod
    def _date_key(unix_ms: int) -> str:
        return datetime.fromtimestamp(unix_ms / 1000, tz=UTC).strftime("%Y-%m-%d")

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return default

    @staticmethod
    def _safe_int(v: Any, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    def _load_local(self) -> list[dict[str, Any]]:
        if not self.local_store.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.local_store.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows

    def _load_supabase(self, days: int) -> list[dict[str, Any]]:
        if not settings.supabase_url.strip() or not settings.supabase_service_role_key.strip():
            return []
        base = settings.supabase_url.rstrip("/")
        table = settings.supabase_checkout_table.strip()
        if not table:
            return []

        since_ms = int(datetime.now(tz=UTC).timestamp() * 1000) - (days * 86400 * 1000)
        params = parse.urlencode(
            {
                "select": "*",
                "checkout_at_unix_ms": f"gte.{since_ms}",
                "order": "checkout_at_unix_ms.asc",
                "limit": "5000",
            }
        )
        req = request.Request(
            url=f"{base}/rest/v1/{table}?{params}",
            method="GET",
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
            },
        )
        with request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body.strip() else []
        return data if isinstance(data, list) else []

    def _load_sessions(self, days: int) -> tuple[list[dict[str, Any]], str]:
        rows: list[dict[str, Any]] = []
        source = "local_jsonl"
        try:
            rows = self._load_supabase(days)
            if rows:
                source = "supabase"
        except Exception:
            rows = []

        if not rows:
            rows = self._load_local()
            now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
            min_ms = now_ms - (days * 86400 * 1000)
            rows = [r for r in rows if self._safe_int(r.get("checkout_at_unix_ms"), 0) >= min_ms]
            source = "local_jsonl"
        return rows, source

    @staticmethod
    def _moving_average(values: list[float], window: int) -> float:
        if not values:
            return 0.0
        w = max(1, min(window, len(values)))
        subset = values[-w:]
        return sum(subset) / len(subset)

    def analyze(self, days: int = 30, top_k: int = 8) -> dict[str, Any]:
        sessions, source = self._load_sessions(days)
        if not sessions:
            return {
                "ok": True,
                "message": "Aucune session panier disponible pour la periode selectionnee.",
                "kpis": {
                    "sessions": 0,
                    "revenue_total": 0.0,
                    "avg_basket": 0.0,
                    "items_sold": 0,
                    "source": source,
                },
                "revenue_candles": [],
                "revenue_trend": [],
                "top_products": [],
                "queue_distribution": {},
                "queue_revenue": {},
                "avg_time_in_store_sec": 0.0,
                "predicted_next_day_revenue": 0.0,
                "stock_risk": [],
                "agent_insights": [],
            }

        by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
        queue_distribution: dict[str, int] = defaultdict(int)
        queue_revenue: dict[str, float] = defaultdict(float)
        product_stats: dict[str, dict[str, Any]] = {}
        durations: list[int] = []
        total_revenue = 0.0
        total_items_qty = 0

        for s in sessions:
            total = self._safe_float(s.get("total_price"), 0.0)
            ts = self._safe_int(s.get("checkout_at_unix_ms"), 0)
            if ts <= 0:
                continue
            dkey = self._date_key(ts)
            by_day[dkey].append({"total_price": total, "checkout_at_unix_ms": ts})
            total_revenue += total

            q = str(s.get("recommended_queue") or "unknown")
            queue_distribution[q] += 1
            queue_revenue[q] += total

            dur = s.get("duration_seconds")
            if isinstance(dur, int) and dur >= 0:
                durations.append(dur)

            items = s.get("items") or []
            if isinstance(items, list):
                for it in items:
                    name = str(it.get("name") or "unknown")
                    brand = str(it.get("brand") or "")
                    qty = self._safe_int(it.get("quantity"), 1)
                    price = self._safe_float(it.get("unit_price"), 0.0)
                    qty = max(1, qty)
                    rev = qty * price
                    total_items_qty += qty
                    key = f"{name}::{brand}"
                    st = product_stats.get(
                        key,
                        {"name": name, "brand": brand, "quantity": 0, "revenue": 0.0, "unit_prices": []},
                    )
                    st["quantity"] += qty
                    st["revenue"] += rev
                    st["unit_prices"].append(price)
                    product_stats[key] = st

        days_sorted = sorted(by_day.keys())
        revenue_candles: list[dict[str, Any]] = []
        revenue_trend: list[dict[str, Any]] = []
        daily_revenues: list[float] = []

        for day in days_sorted:
            tx = sorted(by_day[day], key=lambda x: x["checkout_at_unix_ms"])
            vals = [float(t["total_price"]) for t in tx]
            if not vals:
                continue
            daily_sum = sum(vals)
            daily_revenues.append(daily_sum)
            revenue_candles.append(
                {
                    "date": day,
                    "open": vals[0],
                    "high": max(vals),
                    "low": min(vals),
                    "close": vals[-1],
                    "volume": len(vals),
                }
            )
            revenue_trend.append({"date": day, "value": daily_sum})

        top_products = []
        for st in product_stats.values():
            prices = st.pop("unit_prices", [])
            avg_price = (sum(prices) / len(prices)) if prices else 0.0
            top_products.append(
                {
                    "name": st["name"],
                    "brand": st["brand"],
                    "quantity": int(st["quantity"]),
                    "revenue": float(st["revenue"]),
                    "avg_price": float(avg_price),
                }
            )
        top_products.sort(key=lambda x: (x["revenue"], x["quantity"]), reverse=True)
        top_products = top_products[: max(1, top_k)]

        avg_time = float(sum(durations) / len(durations)) if durations else 0.0
        avg_basket = total_revenue / max(1, len(sessions))
        predicted_next_day_revenue = self._moving_average(daily_revenues, window=7)
        first_week_avg = self._moving_average(daily_revenues[:7], window=7) if daily_revenues else 0.0
        last_week_avg = self._moving_average(daily_revenues[-7:], window=7) if daily_revenues else 0.0
        trend_pct = ((last_week_avg - first_week_avg) / first_week_avg * 100.0) if first_week_avg > 0 else 0.0

        avg_daily_qty_denom = max(1, len(days_sorted))
        stock_risk: list[dict[str, Any]] = []
        for p in top_products[: min(8, len(top_products))]:
            avg_daily_qty = p["quantity"] / avg_daily_qty_denom
            est_stock = 60.0
            days_left = est_stock / max(avg_daily_qty, 0.1)
            if days_left <= 7:
                risk = "high"
            elif days_left <= 14:
                risk = "medium"
            else:
                risk = "low"
            stock_risk.append(
                {
                    "name": p["name"],
                    "brand": p["brand"],
                    "estimated_days_left": round(days_left, 2),
                    "avg_daily_qty": round(avg_daily_qty, 2),
                    "risk_level": risk,
                }
            )
        stock_risk.sort(key=lambda x: x["estimated_days_left"])

        qdrant_marketing_hits: list[str] = []
        for p in top_products[:3]:
            query = f"{p['name']} {p['brand']}".strip()
            matches = qdrant_service.search_products(query=query, top_k=2)
            for m in matches:
                m_name = str(m.get("name") or "").strip()
                if m_name and m_name.lower() != p["name"].lower() and m_name not in qdrant_marketing_hits:
                    qdrant_marketing_hits.append(m_name)
                if len(qdrant_marketing_hits) >= 4:
                    break
            if len(qdrant_marketing_hits) >= 4:
                break

        top_queue = max(queue_distribution.items(), key=lambda kv: kv[1])[0] if queue_distribution else "N/A"
        top_queue_rev = max(queue_revenue.items(), key=lambda kv: kv[1])[0] if queue_revenue else "N/A"
        high_risk = [r for r in stock_risk if r["risk_level"] == "high"]
        high_risk_names = [f"{r['name']} ({r['estimated_days_left']}j)" for r in high_risk[:5]]
        best_day = max(revenue_trend, key=lambda x: x["value"]) if revenue_trend else {"date": "-", "value": 0.0}
        worst_day = min(revenue_trend, key=lambda x: x["value"]) if revenue_trend else {"date": "-", "value": 0.0}

        agent_insights = [
            {
                "agent": "revenue_agent",
                "title": "Analyse Revenue",
                "summary": f"CA total {total_revenue:.2f} TND, panier moyen {avg_basket:.2f} TND, prediction J+1 {predicted_next_day_revenue:.2f} TND.",
                "details": [
                    f"Tendance hebdo estimee: {trend_pct:+.2f}%",
                    f"Meilleur jour: {best_day['date']} ({float(best_day['value']):.2f} TND)",
                    f"Jour le plus faible: {worst_day['date']} ({float(worst_day['value']):.2f} TND)",
                ],
                "recommendations": [
                    "Renforcer la promo sur les 3 meilleurs produits pour pousser le panier moyen.",
                    "Surveiller les jours avec baisse de close sur la courbe chandelle.",
                ],
            },
            {
                "agent": "operations_agent",
                "title": "Analyse Operations",
                "summary": f"Temps moyen magasin {avg_time:.1f}s, caisse recommandee dominante: {top_queue}.",
                "details": [
                    f"Caisse top en revenu: {top_queue_rev}",
                    f"Nombre total de caisses actives: {len(queue_distribution)}",
                    f"Duree mediane non calculee (donnees brutes) - moyenne actuelle {avg_time:.1f}s",
                ],
                "recommendations": [
                    "Ajuster le staffing autour des pics detectes.",
                    "Utiliser la recommandation caisse en temps reel sur mobile client.",
                ],
            },
            {
                "agent": "forecast_agent",
                "title": "Prediction Stock",
                "summary": f"{len(high_risk)} produit(s) en risque stock eleve dans la projection actuelle.",
                "details": [
                    f"Produits analyses pour le risque: {len(stock_risk)}",
                    f"Fenetre historique utilisee: {len(days_sorted)} jours",
                    "Projection basee sur debit moyen journalier observe.",
                    (
                        "Produits a risque: " + ", ".join(high_risk_names)
                        if high_risk_names
                        else "Produits a risque: aucun risque eleve detecte."
                    ),
                ],
                "recommendations": [
                    "Declencher reapprovisionnement prioritaire pour les risques eleves.",
                    "Lancer campagne marketing sur les produits alternatifs pour lisser la demande.",
                ],
            },
            {
                "agent": "qdrant_reco_agent",
                "title": "Recommandation Marketing (Qdrant)",
                "summary": "Suggestions derives des similarites produits dans la collection Qdrant.",
                "details": [
                    "Les suggestions proviennent des voisins semantiques des top ventes.",
                    "Utiliser ces couples pour bundles et cross-sell en rayon/checkout.",
                    (
                        "Produits cibles campagne: " + ", ".join([p["name"] for p in top_products[:3]])
                        if top_products
                        else "Produits cibles campagne: non disponible."
                    ),
                ],
                "recommendations": qdrant_marketing_hits
                if qdrant_marketing_hits
                else ["Qdrant indisponible ou pas assez de donnees pour suggestions croisees."],
            },
        ]

        return {
            "ok": True,
            "message": f"Analyse magasin generee sur {len(sessions)} sessions.",
            "kpis": {
                "sessions": len(sessions),
                "revenue_total": round(total_revenue, 2),
                "avg_basket": round(avg_basket, 2),
                "items_sold": int(total_items_qty),
                "source": source,
            },
            "revenue_candles": revenue_candles,
            "revenue_trend": revenue_trend,
            "top_products": top_products,
            "queue_distribution": dict(queue_distribution),
            "queue_revenue": {k: round(v, 2) for k, v in queue_revenue.items()},
            "avg_time_in_store_sec": round(avg_time, 2),
            "predicted_next_day_revenue": round(predicted_next_day_revenue, 2),
            "stock_risk": stock_risk,
            "agent_insights": agent_insights,
        }


store_analytics_service = StoreAnalyticsService()
