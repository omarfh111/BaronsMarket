from __future__ import annotations

import re
import time
import uuid
from typing import Any

from app.services.catalog_service import catalog_service
from app.services.qdrant_service import qdrant_service

FOOD_CATEGORIES = {"epicerie", "cremerie", "marche", "boissons"}

STOPWORDS = {
    "je", "veux", "svp", "stp", "sil", "s il", "vous", "moi", "mon", "ma", "mes", "de", "des", "du", "la", "le", "les",
    "et", "ou", "pour", "avec", "sans", "dans", "sur", "au", "aux", "en", "un", "une", "a", "d", "l", "donner", "donne",
    "produit", "produits", "acheter", "achat", "liste", "budget", "pas", "cher", "chers", "moins", "plus", "tnd", "dt", "dinar",
}

SLOT_PROMPTS = {
    "people": "Pour combien de personnes ?",
    "budget": "Quel est votre budget (ex: 20 TND) ?",
    "dish": "Quel plat exact voulez-vous preparer ?",
    "goal": "Voulez-vous recette, produits a acheter, ou panier sain semaine ?",
}


class AssistantService:
    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, str]]] = {}
        self._session_state: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _normalize(text: str) -> str:
        t = (text or "").lower().strip()
        repl = {
            "9": "q",
            "é": "e",
            "è": "e",
            "ê": "e",
            "à": "a",
            "â": "a",
            "ô": "o",
            "û": "u",
            "Ã©": "e",
            "Ã¨": "e",
            "Ãª": "e",
            "Ã ": "a",
            "Ã¢": "a",
            "Ã´": "o",
            "Ã»": "u",
        }
        for k, v in repl.items():
            t = t.replace(k, v)
        return t

    @staticmethod
    def _contains_any(text: str, keys: list[str]) -> bool:
        return any(k in text for k in keys)

    @staticmethod
    def _safe_quantity(value: Any) -> int:
        try:
            qty = int(float(str(value).strip()))
        except Exception:
            qty = 1
        return max(1, min(qty, 5))

    @staticmethod
    def _extract_people(text: str, allow_standalone: bool) -> int | None:
        t = text.strip().lower()
        has_hint = bool(re.search(r"\b(personne|personnes|people|adultes?|famille)\b", t))
        if not has_hint and not allow_standalone:
            return None
        m = re.search(r"\b(\d{1,2})\b", t)
        if not m:
            return None
        n = int(m.group(1))
        return n if 1 <= n <= 20 else None

    @staticmethod
    def _extract_budget(text: str, allow_standalone: bool) -> float | None:
        t = text.strip().lower()
        has_hint = bool(re.search(r"\b(budget|tnd|dt|dinar)\b", t))
        if not has_hint and not allow_standalone:
            return None
        m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(tnd|dt|dinar)?", t)
        if not m:
            return None
        try:
            value = float(m.group(1).replace(",", "."))
        except Exception:
            return None
        return value if value >= 0 else None

    @staticmethod
    def _extract_brand(text: str) -> str | None:
        t = text.lower()
        # Generic patterns: "marque randa", "brand x", "de marque x"
        patterns = [
            r"\bmarque\s+([a-z0-9\- ]{2,30})",
            r"\bbrand\s+([a-z0-9\- ]{2,30})",
            r"\bde\s+marque\s+([a-z0-9\- ]{2,30})",
        ]
        for p in patterns:
            m = re.search(p, t)
            if m:
                val = m.group(1).strip()
                if val and val not in {"pas", "moins", "plus"}:
                    return val
        return None

    def _extract_keywords(self, text: str) -> list[str]:
        t = self._normalize(text)
        tokens = [x for x in re.split(r"\W+", t) if x and len(x) >= 3 and x not in STOPWORDS]
        # keep order unique
        out: list[str] = []
        seen: set[str] = set()
        for tok in tokens:
            if tok not in seen:
                seen.add(tok)
                out.append(tok)
        return out[:8]

    def _detect_dish(self, text: str, current: str | None) -> str | None:
        t = self._normalize(text)
        aliases = {
            "burger": ["burger", "hamburger"],
            "spaghetti": ["spaghetti", "spagheti"],
            "ma9rouna": ["ma9rouna", "maqrouna", "makarouna", "pates", "pasta", "macaroni"],
            "omelette": ["omelette", "omlette"],
            "pizza": ["pizza"],
            "couscous": ["couscous", "keskes"],
        }
        for dish, words in aliases.items():
            if any(w in t for w in words):
                return dish
        return current

    def _is_in_scope(self, text: str, state: dict[str, Any]) -> bool:
        if state.get("goal") or state.get("awaiting_slot"):
            return True
        keys = [
            "recette", "prepare", "preparer", "cuisine", "plat", "panier", "budget", "prix", "produit", "produits", "acheter",
            "shopping", "nutrition", "bebe", "caisse", "queue", "garantie", "support", "app", "sain", "semaine", "menu",
            "burger", "spaghetti", "ma9rouna", "omelette", "pizza", "couscous",
        ]
        return self._contains_any(text, keys)

    def _looks_out_of_scope(self, text: str) -> bool:
        # Global guard: if message has no supermarket intent signals, avoid sticky product responses.
        keys = [
            "recette", "prepare", "preparer", "cuisine", "plat", "panier", "budget", "prix", "produit", "produits", "acheter",
            "shopping", "nutrition", "bebe", "caisse", "queue", "garantie", "support", "app", "sain", "semaine", "menu",
            "burger", "spaghetti", "ma9rouna", "omelette", "pizza", "couscous", "marque", "stock", "disponible",
        ]
        return not self._contains_any(text, keys)


    def _detect_goal(self, text: str, current_goal: str | None) -> str | None:
        if self._contains_any(text, ["garantie", "bug", "support", "probleme app", "contact"]):
            return "support"
        if self._contains_any(text, ["panier sain", "1 semaine", "semaine", "healthy", "menu semaine"]):
            return "weekly_plan"
        if self._contains_any(text, ["bebe", "nourrisson"]):
            return "baby_products"
        if self._contains_any(text, ["recette", "comment preparer", "prepare", "preparer", "na3mel", "nheb na3mel", "cuisiner"]):
            return "recipe"
        if self._contains_any(text, ["donner produit", "donne produit", "produits a acheter", "liste produits", "acheter", "shopping list", "pas chers", "moins cher"]):
            if current_goal == "weekly_plan":
                return "weekly_plan"
            return "product_search"
        return current_goal

    def _route_agent(self, state: dict[str, Any]) -> str:
        goal = state.get("goal")
        if goal == "support":
            return "support"
        if goal == "weekly_plan":
            return "nutrition_generale"
        if goal == "baby_products":
            return "nutrition_bebe"
        if goal == "recipe":
            return "chef"
        if goal == "product_search":
            return "general"
        return "general"

    @staticmethod
    def _queries_for_known_dish(dish: str | None) -> list[dict[str, Any]]:
        if dish == "burger":
            return [
                {"name": "pain burger", "quantity": 1, "reason": "Base"},
                {"name": "viande hachee", "quantity": 1, "reason": "Proteine"},
                {"name": "fromage burger", "quantity": 1, "reason": "Garniture"},
                {"name": "tomate", "quantity": 1, "reason": "Garniture"},
                {"name": "salade", "quantity": 1, "reason": "Garniture"},
            ]
        if dish in {"spaghetti", "ma9rouna"}:
            return [
                {"name": "spaghetti", "quantity": 1, "reason": "Base"},
                {"name": "sauce tomate", "quantity": 1, "reason": "Sauce"},
                {"name": "oignon", "quantity": 1, "reason": "Aromatique"},
                {"name": "ail", "quantity": 1, "reason": "Aromatique"},
                {"name": "fromage rape", "quantity": 1, "reason": "Option"},
            ]
        if dish == "omelette":
            return [
                {"name": "oeufs", "quantity": 1, "reason": "Base"},
                {"name": "fromage", "quantity": 1, "reason": "Option"},
                {"name": "oignon", "quantity": 1, "reason": "Option"},
                {"name": "tomate", "quantity": 1, "reason": "Option"},
            ]
        return []

    def _queries_for_weekly(self, budget: float | None) -> list[dict[str, Any]]:
        if budget is not None and budget <= 30:
            return [
                {"name": "legumes saison", "quantity": 1, "reason": "Economique"},
                {"name": "fruits saison", "quantity": 1, "reason": "Economique"},
                {"name": "lentilles", "quantity": 1, "reason": "Proteine abordable"},
                {"name": "riz", "quantity": 1, "reason": "Base repas"},
                {"name": "yaourt nature", "quantity": 1, "reason": "Petit dejeuner"},
            ]
        return [
            {"name": "legumes saison", "quantity": 2, "reason": "Base saine"},
            {"name": "fruits saison", "quantity": 2, "reason": "Base saine"},
            {"name": "thon", "quantity": 1, "reason": "Proteine"},
            {"name": "riz complet", "quantity": 1, "reason": "Cereale complete"},
            {"name": "yaourt nature", "quantity": 1, "reason": "Petit dejeuner"},
        ]

    @staticmethod
    def _queries_for_baby() -> list[dict[str, Any]]:
        return [
            {"name": "lait bebe", "quantity": 1, "reason": "Essentiel"},
            {"name": "cereales bebe", "quantity": 1, "reason": "Petit dejeuner"},
            {"name": "compote bebe", "quantity": 1, "reason": "Gouter"},
            {"name": "puree bebe", "quantity": 1, "reason": "Repas"},
        ]

    def _build_queries(self, state: dict[str, Any], text: str) -> list[dict[str, Any]]:
        goal = state.get("goal")
        if goal == "weekly_plan":
            return self._queries_for_weekly(state.get("budget"))
        if goal == "baby_products":
            return self._queries_for_baby()

        dish_queries = self._queries_for_known_dish(state.get("dish"))
        if dish_queries:
            return dish_queries

        # Generic fallback: build from user keywords (not hardcoded cases)
        keywords = self._extract_keywords(text)
        if not keywords:
            keywords = self._extract_keywords(state.get("last_user_message", ""))
        queries: list[dict[str, Any]] = []
        for kw in keywords[:5]:
            queries.append({"name": kw, "quantity": 1, "reason": "Demande utilisateur"})
        if not queries:
            queries = [{"name": "produits pas chers", "quantity": 1, "reason": "Demande utilisateur"}]
        return queries

    def _search_best(self, query: str, brand: str | None, food_only: bool) -> list[dict[str, Any]]:
        q = self._normalize(query)
        tokens = [t for t in re.split(r"\W+", q) if t]
        brand_n = self._normalize(brand or "")

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in catalog_service.all_products():
            category = str(item.get("category", "")).lower()
            if food_only and category not in FOOD_CATEGORIES:
                continue
            text = self._normalize(f"{item.get('name', '')} {item.get('brand', '')} {category}")
            if brand_n and brand_n not in text:
                continue
            overlap = sum(1 for tok in tokens if tok in text)
            if overlap == 0:
                continue
            score = overlap * 3
            if q in text:
                score += 3
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        picks = [it for _, it in scored[:10]]

        # Qdrant fallback
        if not picks:
            q_items = qdrant_service.search_products(query=query, top_k=10)
            for it in q_items:
                category = str(it.get("category", "")).lower()
                if food_only and category not in FOOD_CATEGORIES:
                    continue
                it_text = self._normalize(f"{it.get('name', '')} {it.get('brand', '')}")
                if brand_n and brand_n not in it_text:
                    continue
                picks.append(it)
                if len(picks) >= 10:
                    break

        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for it in picks:
            pid = str(it.get("id"))
            if pid in seen:
                continue
            path = catalog_service.get_image_path(pid)
            if path is None or not path.exists():
                continue
            seen.add(pid)
            out.append(it)
            if len(out) >= 5:
                break
        return out

    def _resolve_products(self, queries: list[dict[str, Any]], brand: str | None, food_only: bool) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for q in queries[:10]:
            name = str(q.get("name") or "").strip()
            if not name:
                continue
            cands = self._search_best(name, brand=brand, food_only=food_only)
            if not cands:
                continue
            pick = cands[0]
            pid = str(pick.get("id"))
            if pid in seen:
                continue
            seen.add(pid)
            out.append(
                {
                    "id": pid,
                    "name": pick.get("name", ""),
                    "brand": pick.get("brand", ""),
                    "price": float(pick.get("price", 0.0)),
                    "image": pick.get("image", ""),
                    "quantity": self._safe_quantity(q.get("quantity")),
                    "reason": str(q.get("reason") or "Suggestion"),
                }
            )
        return out

    def _capture_entities(self, state: dict[str, Any], text: str, budget_tnd: float | None) -> None:
        awaiting = state.get("awaiting_slot")

        p = self._extract_people(text, allow_standalone=(awaiting == "people"))
        if p is not None:
            state["people"] = p

        b = self._extract_budget(text, allow_standalone=(awaiting == "budget"))
        if b is not None:
            state["budget"] = b

        explicit_budget = bool(re.search(r"\b(budget|tnd|dt|dinar)\b", text))
        if budget_tnd is not None and (awaiting == "budget" or explicit_budget):
            state["budget"] = budget_tnd

        brand = self._extract_brand(text)
        if brand:
            state["brand"] = brand

        prev_dish = state.get("dish")
        dish = self._detect_dish(text, prev_dish)
        # reset brand if dish changed and no new brand in same message
        if dish and prev_dish and dish != prev_dish and not brand:
            state["brand"] = None
        state["dish"] = dish

    def _next_missing_slot(self, state: dict[str, Any]) -> str | None:
        for slot in state.get("required_slots", []):
            if slot == "people" and state.get("people") is None:
                return "people"
            if slot == "budget" and state.get("budget") is None:
                return "budget"
            if slot == "dish" and state.get("dish") is None:
                return "dish"
            if slot == "goal" and state.get("goal") is None:
                return "goal"
        return None

    def _is_affirmation(self, text: str) -> bool:
        return text in {"ok", "oui", "yes", "go", "daccord", "d'accord", "vas y"}

    def _set_plan_from_goal(self, state: dict[str, Any]) -> None:
        goal = state.get("goal")
        if goal == "weekly_plan":
            state["required_slots"] = ["people", "budget"]
        elif goal == "recipe":
            state["required_slots"] = ["dish"]
        elif goal in {"product_search", "baby_products"}:
            state["required_slots"] = []
        elif goal == "support":
            state["required_slots"] = []
        else:
            state["required_slots"] = ["goal"]

    def chat(self, user_message: str, session_id: str | None, budget_tnd: float | None, cart_items: list[dict[str, Any]]) -> dict[str, Any]:
        sid = session_id or str(uuid.uuid4())
        thread = self._history.get(sid, [])
        state = self._session_state.get(
            sid,
            {
                "agent": "general",
                "goal": None,
                "required_slots": ["goal"],
                "awaiting_slot": None,
                "dish": None,
                "brand": None,
                "people": None,
                "budget": None,
                "restrictions": None,
                "last_intent": "chat",
                "last_product_queries": [],
                "last_user_message": "",
            },
        )

        text = self._normalize(user_message)
        state["last_user_message"] = text

        self._capture_entities(state, text, budget_tnd)

        if state.get("awaiting_slot") is None and self._looks_out_of_scope(text):
            state["goal"] = None
            state["required_slots"] = ["goal"]

        detected_goal = self._detect_goal(text, state.get("goal"))
        if detected_goal:
            state["goal"] = detected_goal
        self._set_plan_from_goal(state)
        state["agent"] = self._route_agent(state)

        assistant_message = ""
        steps: list[str] = []
        show_products_now = False
        recommended_products: list[dict[str, Any]] = []

        if not self._is_in_scope(text, state):
            assistant_message = "Je peux aider pour supermarche: verifier disponibilite produit, recommandations, recettes, budget, panier, ou support app."
            steps = ["Expliquez le besoin supermarche.", "Donnez budget si utile.", "Je propose ensuite des produits concrets."]
            state["last_intent"] = "out_of_scope"
        elif state.get("goal") == "support":
            assistant_message = "Je peux aider pour support app, garantie ou probleme technique."
            steps = ["Decrire le probleme.", "Donner detail ou capture.", "Je propose la resolution."]
            state["last_intent"] = "support"
        else:
            missing = self._next_missing_slot(state)
            if missing is not None:
                state["awaiting_slot"] = missing
                assistant_message = SLOT_PROMPTS[missing]
                steps = ["Repondez juste a cette question.", "Je continue automatiquement ensuite."]
                state["last_intent"] = "slot_collection"
            else:
                state["awaiting_slot"] = None

                needs_products = False
                if state.get("goal") in {"product_search", "baby_products"}:
                    needs_products = True
                if state.get("goal") == "weekly_plan" and (self._is_affirmation(text) or self._contains_any(text, ["donner produits", "liste produits", "pas chers"])):
                    needs_products = True
                if state.get("goal") != "recipe" and state.get("last_intent") == "product_search" and (state.get("brand") is not None or self._contains_any(text, ["autre", "marque"])):
                    needs_products = True

                if needs_products:
                    queries = self._build_queries(state, text)
                    state["last_product_queries"] = queries
                    recommended_products = self._resolve_products(queries, brand=state.get("brand"), food_only=True)
                    if not recommended_products and state.get("brand"):
                        recommended_products = self._resolve_products(queries, brand=None, food_only=True)
                        assistant_message = "Je n'ai pas trouve de correspondance forte pour cette marque. Voici les alternatives les plus proches."
                    elif not recommended_products:
                        assistant_message = "Je n'ai pas trouve des produits suffisants pour cette demande. Reformulez le besoin (plat/marque/budget)."
                    else:
                        assistant_message = "Voici les produits recommandes selon votre besoin."
                    steps = ["Verifier les produits.", "Ajuster quantites.", "Ajouter au panier."]
                    show_products_now = len(recommended_products) > 0
                    state["last_intent"] = "product_search"
                elif state.get("goal") == "recipe":
                    budget_txt = f" Budget note: {state.get('budget')} TND." if state.get("budget") is not None else ""
                    assistant_message = f"Je peux vous guider recette etape par etape pour {state.get('dish')}.{budget_txt} Quand vous voulez la liste d'achat, dites: donner produits."
                    steps = ["Suivre les etapes recette.", "Demander produits a acheter.", "Ajouter au panier."]
                    state["last_intent"] = "recipe"
                elif state.get("goal") == "weekly_plan":
                    assistant_message = f"J'ai note {state.get('people')} personne(s) et budget {state.get('budget')} TND. Dites: donner produits pas chers."
                    steps = ["Confirmer generation produits.", "Recevoir la liste.", "Ajouter au panier."]
                    state["last_intent"] = "weekly_ready"
                else:
                    assistant_message = "Dites-moi votre besoin exact: recette, produits a acheter, panier sain semaine, ou support."
                    steps = ["Preciser l'objectif.", "Donner budget si besoin.", "Je fournis resultat concret."]
                    state["last_intent"] = "chat"

        thread.append({"role": "user", "content": user_message, "agent": state.get("agent", "general"), "ts": str(time.time())})
        thread.append({"role": "assistant", "content": assistant_message, "agent": state.get("agent", "general"), "ts": str(time.time())})

        self._history[sid] = thread
        self._session_state[sid] = state

        return {
            "session_id": sid,
            "active_agent": state.get("agent", "general"),
            "assistant_message": assistant_message,
            "mode": "step_by_step",
            "steps": steps,
            "show_products_now": show_products_now,
            "recommended_products": recommended_products,
        }


assistant_service = AssistantService()
