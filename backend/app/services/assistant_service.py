from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from urllib import error, request

from app.core.config import settings
from app.services.catalog_service import catalog_service
from app.services.qdrant_service import qdrant_service


AGENT_CATALOG: dict[str, str] = {
    "general": (
        "Assistant friendly et humain. Il accueille le client, comprend son besoin, "
        "cherche des produits existants, recommande des produits disponibles, et aide a ajouter au panier."
    ),
    "chef": (
        "Agent cuisine. Il transforme une demande de plat ou recette en conseils simples "
        "et peut demander les produits/ingredients disponibles dans le catalogue."
    ),
    "nutrition_generale": (
        "Agent nutrition generale. Il aide pour panier sain, planning repas, budget, quantites et alternatives."
    ),
    "nutrition_bebe": (
        "Agent nutrition bebe. Il aide pour produits bebe et recommandations prudentes selon le besoin du parent."
    ),
    "support": (
        "Agent support. Il aide pour probleme application, paiement, panier, garantie ou experience client."
    ),
}


@dataclass
class RoutePlan:
    agent: str = "general"
    intent: str = ""
    answer: str = ""
    steps: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)
    search_queries: list[dict[str, Any]] = field(default_factory=list)
    needs_products: bool = False
    product_limit: int = 6
    product_display_mode: str = "recommendations"
    memory: dict[str, Any] = field(default_factory=dict)


class LlmClient:
    def __init__(self) -> None:
        self.api_key = settings.openai_api_key.strip()
        self.model = settings.openai_model
        self.base_url = settings.openai_base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def json_chat(self, system: str, user: str) -> dict[str, Any]:
        if not self.configured:
            return {}

        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return {}

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


class SearchTranslatorAgent:
    def __init__(self, llm: LlmClient) -> None:
        self.llm = llm

    def translate(self, plan: RoutePlan, state: dict[str, Any]) -> list[dict[str, Any]]:
        categories = catalog_service.list_products(page=1, page_size=1).get("categories", [])
        parsed = self.llm.json_chat(
            system=self._system_prompt(),
            user=json.dumps(
                {
                    "agent": plan.agent,
                    "intent": plan.intent,
                    "product_display_mode": plan.product_display_mode,
                    "original_queries": plan.search_queries,
                    "conversation_memory": state,
                    "catalog_categories": categories,
                    "catalog_snapshot": self._catalog_snapshot(categories),
                },
                ensure_ascii=False,
            ),
        )
        queries = parsed.get("queries") if isinstance(parsed, dict) else None
        if isinstance(queries, list) and queries:
            return [query for query in queries if isinstance(query, dict)][:12]
        return plan.search_queries

    @staticmethod
    def _system_prompt() -> str:
        return """
Tu es SearchTranslatorAgent pour Qdrant et catalogue produit.
Tu recois l'intention client et les requetes initiales.
Retourne uniquement un JSON valide:
{
  "queries": [
    {
      "query": "requete courte optimisee catalogue/qdrant",
      "quantity": 1,
      "reason": "raison lisible client",
      "category_hints": ["categories possibles depuis catalog_categories"]
    }
  ]
}

Objectif:
- Traduire le besoin naturel en requetes produit courtes et utiles.
- Pour recette ou panier, produire plusieurs requetes complementaires.
- Pour recherche produit simple, produire quelques variantes proches.
- Utiliser catalog_categories pour choisir des termes plausibles du catalogue.
- Si le client demande un plat local, decomposer en ingredients generiques recherchables.
- Produire des requetes de produits concrets et consommables, pas des requetes larges de categorie.
- Eviter les requetes qui peuvent matcher des outils, cosmetiques ou objets non alimentaires quand le besoin est alimentaire.
- Pour chef, preparer un panier complet pour la recette: base, sauce, proteine si utile, legumes/aromates, assaisonnement, option.
- Pour chef, ne demande pas au client de choisir les ingredients si le plat est deja donne; choisis un panier coherent depuis le catalogue.
- Pour chef avec product_display_mode=recipe_ingredients, chaque requete doit correspondre a un ingredient necessaire de la recette.
- Pour chef, eviter les alternatives multiples du meme ingredient sauf si un ingredient principal manque.
- Utilise category_hints pour guider la recherche vers les bonnes categories du catalogue.
- Ne jamais inventer de produit final: ce sont seulement des requetes de recherche.
""".strip()

    @staticmethod
    def _catalog_snapshot(categories: list[str]) -> dict[str, list[str]]:
        products = catalog_service.all_products()
        snapshot: dict[str, list[str]] = {}
        wanted = set(categories)
        for item in products:
            category = str(item.get("category", ""))
            if wanted and category not in wanted:
                continue
            bucket = snapshot.setdefault(category, [])
            if len(bucket) < 5:
                name = str(item.get("name", "")).strip()
                brand = str(item.get("brand", "")).strip()
                label = f"{name} - {brand}" if brand else name
                if label and label not in bucket:
                    bucket.append(label)
            if len(snapshot) >= len(categories) and all(len(values) >= 5 for values in snapshot.values()):
                break
        return snapshot


class ProductResolver:
    def retrieve(self, queries: list[dict[str, Any]], limit: int = 36) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query_index, query in enumerate(queries):
            query_text = str(query.get("query") or query.get("name") or "").strip()
            if not query_text:
                continue
            per_query_count = 0
            for item in self._rank_candidates(query_text, query):
                product_id = str(item.get("id", ""))
                if not product_id or product_id in seen:
                    continue
                seen.add(product_id)
                item = dict(item)
                item["_rag_reason"] = str(query.get("reason") or "Produit candidat")
                item["_rag_quantity"] = query.get("quantity", 1)
                item["_rag_query_index"] = query_index
                candidates.append(item)
                per_query_count += 1
                if len(candidates) >= limit:
                    return candidates
                if per_query_count >= 4:
                    break
        return candidates

    def select_products(
        self,
        candidates: list[dict[str, Any]],
        selected_ids: list[str],
        reasons: dict[str, str],
        limit: int,
        strict_selected: bool = False,
    ) -> list[dict[str, Any]]:
        by_id = {str(item.get("id", "")): item for item in candidates}
        ordered_ids = [pid for pid in selected_ids if pid in by_id]
        if not ordered_ids:
            if strict_selected:
                covered_groups: set[Any] = set()
                for item in candidates:
                    group = item.get("_rag_query_index")
                    product_id = str(item.get("id", ""))
                    if not product_id or group in covered_groups:
                        continue
                    ordered_ids.append(product_id)
                    covered_groups.add(group)
                    if len(ordered_ids) >= limit:
                        break
            else:
                ordered_ids = [str(item.get("id", "")) for item in candidates]
        elif strict_selected:
            covered_groups = {
                by_id[pid].get("_rag_query_index")
                for pid in ordered_ids
                if pid in by_id
            }
            for item in candidates:
                group = item.get("_rag_query_index")
                product_id = str(item.get("id", ""))
                if group in covered_groups or product_id in ordered_ids:
                    continue
                ordered_ids.append(product_id)
                covered_groups.add(group)
                if len(ordered_ids) >= limit:
                    break
        else:
            covered_groups = {
                by_id[pid].get("_rag_query_index")
                for pid in ordered_ids
                if pid in by_id
            }
            for item in candidates:
                group = item.get("_rag_query_index")
                product_id = str(item.get("id", ""))
                if group in covered_groups or product_id in ordered_ids:
                    continue
                ordered_ids.append(product_id)
                covered_groups.add(group)
                if len(ordered_ids) >= limit:
                    break
            for item in candidates:
                product_id = str(item.get("id", ""))
                if product_id not in ordered_ids:
                    ordered_ids.append(product_id)

        products: list[dict[str, Any]] = []
        seen: set[str] = set()
        seen_labels: set[str] = set()
        for product_id in ordered_ids:
            if product_id in seen:
                continue
            item = by_id[product_id]
            label = self._normalize(f"{item.get('name', '')} {item.get('brand', '')}")
            if label in seen_labels:
                continue
            seen.add(product_id)
            seen_labels.add(label)
            products.append(self._format_product(item, {"reason": reasons.get(product_id) or item.get("_rag_reason"), "quantity": item.get("_rag_quantity", 1)}))
            if len(products) >= limit:
                break
        return products

    def _rank_candidates(self, query: str, query_meta: dict[str, Any]) -> list[dict[str, Any]]:
        merged: list[tuple[float, dict[str, Any]]] = []
        seen: set[str] = set()
        category_hints = {
            self._normalize(str(category))
            for category in query_meta.get("category_hints", [])
            if str(category).strip()
        }
        for source_weight, candidates in (
            (1.2, self._qdrant_candidates(query)),
            (1.0, self._catalog_candidates(query)),
        ):
            for rank, item in enumerate(candidates):
                product_id = str(item.get("id", ""))
                if not product_id or product_id in seen:
                    continue
                seen.add(product_id)
                text = self._normalize(f"{item.get('name', '')} {item.get('brand', '')} {item.get('category', '')}")
                score = self._similarity(self._normalize(query), text) * source_weight
                category = self._normalize(str(item.get("category", "")))
                if category_hints and category in category_hints:
                    score += 0.18
                score += max(0.0, 0.2 - (rank * 0.015))
                merged.append((score, item))
        merged.sort(key=lambda value: value[0], reverse=True)
        return [item for _, item in merged[:12]]

    def _catalog_candidates(self, query: str) -> list[dict[str, Any]]:
        normalized_query = self._normalize(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in catalog_service.all_products():
            text = self._normalize(
                f"{item.get('name', '')} {item.get('brand', '')} {item.get('category', '')}"
            )
            score = self._similarity(normalized_query, text)
            if normalized_query and normalized_query in text:
                score += 0.35
            if score >= 0.22:
                scored.append((score, item))
        scored.sort(key=lambda value: value[0], reverse=True)
        return [item for _, item in scored[:8]]

    @staticmethod
    def _qdrant_candidates(query: str) -> list[dict[str, Any]]:
        try:
            return qdrant_service.search_products(query=query, top_k=8)
        except Exception:
            return []

    @staticmethod
    def _format_product(item: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
        quantity = query.get("quantity", 1)
        try:
            quantity = int(float(str(quantity)))
        except Exception:
            quantity = 1
        return {
            "id": str(item.get("id", "")),
            "name": str(item.get("name", "")),
            "brand": str(item.get("brand", "")),
            "price": float(item.get("price", 0.0) or 0.0),
            "image": str(item.get("image", "")),
            "quantity": max(1, min(quantity, 10)),
            "reason": str(query.get("reason") or item.get("_rag_reason") or "Suggestion adaptee a votre demande"),
        }

    @staticmethod
    def _normalize(value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"\s+", " ", value)
        return value

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        left_terms = set(re.findall(r"\w+", left))
        right_terms = set(re.findall(r"\w+", right))
        overlap = len(left_terms & right_terms) / max(1, len(left_terms))
        ratio = SequenceMatcher(None, left, right[: max(len(left) * 2, 80)]).ratio()
        return (overlap * 0.7) + (ratio * 0.3)


class RouterAgent:
    def __init__(self, llm: LlmClient) -> None:
        self.llm = llm

    def route(self, *, message: str, state: dict[str, Any], cart_items: list[dict[str, Any]]) -> RoutePlan:
        parsed = self.llm.json_chat(
            system=self._system_prompt(),
            user=json.dumps(
                {
                    "message": message,
                    "conversation_state": state,
                    "cart_items": cart_items,
                    "available_agents": AGENT_CATALOG,
                },
                ensure_ascii=False,
            ),
        )
        return self._plan_from_json(parsed, message)

    @staticmethod
    def _system_prompt() -> str:
        return """
Tu es RouterAgent pour un assistant de supermarche multi-agent.
Tu ne reponds jamais en texte libre: tu retournes uniquement un JSON valide.

Objectif:
- Comprendre le message client et le contexte conversationnel.
- Choisir l'agent le plus utile parmi available_agents.
- Traduire la demande en intention claire.
- Generer des requetes catalogue generales si des produits doivent etre affiches.

Contrat JSON strict:
{
  "agent": "general|chef|nutrition_generale|nutrition_bebe|support",
  "intent": "resume court de l'intention client",
  "answer": "reponse courte, chaleureuse, utile, en francais simple",
  "steps": ["etapes detaillees ou prochaines actions utiles"],
  "guidance": ["conseils detailles utiles selon l'agent"],
  "needs_products": true/false,
    "search_queries": [
    {"query": "terme de recherche catalogue", "quantity": 1, "reason": "raison client"}
  ],
  "product_limit": 1-12,
  "product_display_mode": "recommendations|recipe_ingredients|shopping_basket",
  "memory": {"cles utiles a conserver": "valeurs"}
}

Regles:
- L'agent general est l'entree par defaut: il assiste, cherche l'existence de produits et recommande des produits disponibles.
- Si le client demande des produits existants, mets needs_products=true et cree des search_queries.
- Si le client utilise "affiche les produits", "donne produits", "ajouter au panier", "liste produits" ou equivalent, needs_products doit etre true.
- Si le client demande un nombre de produits, mets product_limit a ce nombre. Sinon choisis un nombre raisonnable selon le besoin.
- Pour une recette ou un panier, cree plusieurs search_queries complementaires.
- Pour une recette avec demande de produits, cree des requetes d'ingredients probables meme si tu poses une question de preference.
- Donne dans steps/guidance assez de detail pour que l'assistant soit vraiment utile, surtout pour recette, nutrition et support.
- Pour chef: si le client donne un plat/recette, prepare directement une recette complete et un panier complet. Ne demande pas au client de choisir les ingredients.
- Pour chef: product_limit doit etre 8 a 12 quand le client demande les produits/ingredients.
- Pour chef: product_display_mode doit etre "recipe_ingredients". Les produits affiches sont les ingredients du panier de la recette, pas des recommandations alternatives.
- Ne fabrique pas de produits. Les produits affiches viennent seulement du catalogue.
- Si une information manque, pose une seule question dans answer et laisse needs_products=false.
- Ne mets pas de logique codee en dur dans la reponse; deduis depuis le contexte.
""".strip()

    @staticmethod
    def _plan_from_json(parsed: dict[str, Any], message: str) -> RoutePlan:
        if not parsed:
            return RoutePlan(
                agent="general",
                intent=message,
                answer="Je vais chercher dans le catalogue les produits les plus proches de votre demande.",
                steps=["Verifier les suggestions.", "Preciser le besoin si le resultat n'est pas assez proche."],
                guidance=["Je peux affiner par marque, budget, usage, quantite ou preference."],
                search_queries=[{"query": message, "quantity": 1, "reason": "Demande client"}],
                needs_products=True,
                product_limit=6,
                product_display_mode="recommendations",
            )

        agent = str(parsed.get("agent") or "general")
        if agent not in AGENT_CATALOG:
            agent = "general"

        queries = parsed.get("search_queries") or []
        if not isinstance(queries, list):
            queries = []

        steps = parsed.get("steps") or []
        if not isinstance(steps, list):
            steps = []

        guidance = parsed.get("guidance") or []
        if not isinstance(guidance, list):
            guidance = []

        memory = parsed.get("memory") or {}
        if not isinstance(memory, dict):
            memory = {}

        return RoutePlan(
            agent=agent,
            intent=str(parsed.get("intent") or message),
            answer=str(parsed.get("answer") or "Je suis la pour vous aider. Dites-moi ce que vous cherchez."),
            steps=[str(step) for step in steps[:8]],
            guidance=[str(item) for item in guidance[:8]],
            search_queries=[q for q in queries if isinstance(q, dict)][:8],
            needs_products=bool(parsed.get("needs_products")),
            product_limit=RouterAgent._clean_product_limit(parsed.get("product_limit")),
            product_display_mode=RouterAgent._clean_display_mode(parsed.get("product_display_mode"), agent),
            memory=memory,
        )

    @staticmethod
    def _clean_product_limit(value: Any) -> int:
        try:
            number = int(float(str(value)))
        except Exception:
            number = 6
        return max(1, min(number, 12))

    @staticmethod
    def _clean_display_mode(value: Any, agent: str) -> str:
        mode = str(value or "").strip()
        allowed = {"recommendations", "recipe_ingredients", "shopping_basket"}
        if mode in allowed:
            return mode
        return "recipe_ingredients" if agent == "chef" else "recommendations"


class ResponseAgent:
    def __init__(self, llm: LlmClient, resolver: ProductResolver, search_translator: SearchTranslatorAgent) -> None:
        self.llm = llm
        self.resolver = resolver
        self.search_translator = search_translator

    def handle(self, plan: RoutePlan, state: dict[str, Any]) -> dict[str, Any]:
        translated_queries = self.search_translator.translate(plan, state) if plan.needs_products else []
        candidates = self.resolver.retrieve(translated_queries) if plan.needs_products else []
        rag = self._rag_answer(plan, translated_queries, candidates)
        selected_ids = [str(pid) for pid in rag.get("selected_product_ids", []) if str(pid)]
        reasons = rag.get("product_reasons") if isinstance(rag.get("product_reasons"), dict) else {}
        products = (
            self.resolver.select_products(
                candidates,
                selected_ids,
                reasons,
                limit=plan.product_limit,
                strict_selected=plan.product_display_mode == "recipe_ingredients",
            )
            if plan.needs_products
            else []
        )
        answer = self._compose_final_answer(plan, products, rag)
        state.update(plan.memory)
        state["last_agent"] = plan.agent
        state["last_intent"] = plan.intent
        state["last_search_queries"] = translated_queries
        state["last_rag_product_ids"] = [p["id"] for p in products]

        return {
            "active_agent": plan.agent,
            "assistant_message": answer,
            "mode": "step_by_step",
            "steps": self._merge_steps(rag.get("steps"), plan.steps, plan.guidance),
            "show_products_now": bool(products),
            "recommended_products": products,
        }

    @staticmethod
    def _merge_steps(primary: Any, fallback: list[str], guidance: list[str]) -> list[str]:
        source = primary if isinstance(primary, list) and primary else fallback
        merged: list[str] = []
        for item in [*source, *guidance]:
            text = str(item).strip()
            if text and text not in merged:
                merged.append(text)
        return merged[:10]

    def _rag_answer(self, plan: RoutePlan, queries: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        if not plan.needs_products:
            parsed = self.llm.json_chat(
                system=self._advice_system_prompt(plan.agent),
                user=json.dumps(
                    {
                        "agent": plan.agent,
                        "intent": plan.intent,
                        "draft_answer": plan.answer,
                        "draft_steps": plan.steps,
                        "guidance": plan.guidance,
                    },
                    ensure_ascii=False,
                ),
            )
            return parsed or {"answer": plan.answer, "steps": plan.steps, "selected_product_ids": []}
        context_products = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "brand": item.get("brand"),
                "price": item.get("price"),
                "category": item.get("category"),
                "retrieval_reason": item.get("_rag_reason"),
                "query_group": item.get("_rag_query_index"),
            }
            for item in candidates[:36]
        ]
        parsed = self.llm.json_chat(
            system=self._rag_system_prompt(plan.agent),
            user=json.dumps(
                {
                    "agent": plan.agent,
                    "intent": plan.intent,
                    "draft_answer": plan.answer,
                    "requested_product_limit": plan.product_limit,
                    "product_display_mode": plan.product_display_mode,
                    "queries": queries,
                    "product_context": context_products,
                },
                ensure_ascii=False,
            ),
        )
        if parsed:
            return parsed
        return {
            "answer": plan.answer,
            "steps": plan.steps,
            "selected_product_ids": [str(item.get("id")) for item in candidates[: plan.product_limit]],
            "product_reasons": {},
        }

    @staticmethod
    def _rag_system_prompt(agent: str) -> str:
        return f"""
Tu es l'agent {agent} dans une architecture RAG agentique pour supermarche.
Tu dois repondre seulement avec les informations de product_context.
Tu ne dois jamais inventer un produit, une marque ou un prix.
Tu peux donner des conseils generaux, mais les produits selectionnes doivent venir uniquement de product_context.

Retourne uniquement ce JSON:
{{
  "answer": "reponse finale complete, utile et detaillee en francais",
  "steps": ["etapes concretes, detaillees et ordonnees"],
  "selected_product_ids": ["ids choisis depuis product_context uniquement"],
  "product_reasons": {{"product_id": "raison specifique liee au besoin client"}}
}}

Regles:
- Si product_context est vide, selected_product_ids doit etre [] et answer doit demander une precision.
- Respecte requested_product_limit.
- Si assez de produits pertinents existent dans product_context, selectionne requested_product_limit IDs.
- Ne selectionne pas un produit non coherent seulement pour remplir le nombre.
- Pour chef: selectionne des produits qui aident vraiment la recette.
- Pour chef: donne une recette claire avec ingredients recommandes, preparation etapes par etapes, conseils de cuisson.
- Pour chef: n'ecris jamais "quels ingredients voulez-vous inclure" si l'intention contient deja un plat. Compose toi-meme un panier complet a partir de product_context.
- Pour chef: structure answer avec "Ingredients de la recette", "Preparation", "Conseil".
- Pour chef: couvre plusieurs query_group differents pour construire un panier complet, pas plusieurs variantes du meme ingredient.
- Pour chef avec product_display_mode=recipe_ingredients: selected_product_ids doit representer les ingredients de la recette, pas des recommandations ou alternatives.
- Pour nutrition: privilegie coherence, equilibre et budget si mentionne.
- Pour nutrition: donne un plan ou des conseils applicables, pas seulement une liste produit.
- Pour support: donne diagnostic, causes possibles et actions de resolution.
- Pour general: privilegie correspondance exacte avec la recherche.
- Pour general: verifie le sens reel, pas seulement les mots. Exemple: "fruits de mer" n'est pas un fruit pour petit dejeuner.
- Exclue les produits incoherents avec le moment d'usage ou la recette meme s'ils partagent un mot.
- Si tu cites un prix, utilise TND et seulement les prix fournis dans product_context.
""".strip()

    @staticmethod
    def _advice_system_prompt(agent: str) -> str:
        return f"""
Tu es l'agent {agent} d'un assistant supermarche complet.
Tu dois aider concretement, avec detail, en francais simple.
Tu peux donner une recette, un plan, des conseils ou une procedure.
Si tu parles de produits precis, indique que tu peux les chercher dans le catalogue au prochain message.

Retourne uniquement ce JSON:
{{
  "answer": "reponse complete et utile",
  "steps": ["etapes detaillees"],
  "selected_product_ids": [],
  "product_reasons": {{}}
}}
""".strip()

    def _compose_final_answer(self, plan: RoutePlan, products: list[dict[str, Any]], rag: dict[str, Any]) -> str:
        if products:
            return self._deterministic_product_answer(plan, products, rag)
        if plan.needs_products:
            return "Je n'ai pas trouve de produit suffisamment proche dans le catalogue. Reformulez avec une marque, un nom produit, ou un besoin plus precis."
        return plan.answer

    def _deterministic_product_answer(self, plan: RoutePlan, products: list[dict[str, Any]], rag: dict[str, Any]) -> str:
        if plan.product_display_mode == "recipe_ingredients":
            count_note = f"J'ai prepare {len(products)} ingredient(s) disponible(s) dans notre catalogue"
        else:
            count_note = f"J'ai trouve {len(products)} produit(s) disponible(s) dans notre catalogue"
        if len(products) < plan.product_limit:
            count_note += f" sur {plan.product_limit} demande(s) pertinentes"

        product_lines = []
        for index, product in enumerate(products, start=1):
            name = str(product.get("name", "")).strip()
            brand = str(product.get("brand", "")).strip()
            price = float(product.get("price", 0.0) or 0.0)
            reason = str(product.get("reason", "")).strip()
            line = f"{index}. {name}"
            if brand:
                line += f" - {brand}"
            line += f" ({price:.2f} TND)"
            if reason:
                line += f": {reason}"
            product_lines.append(line)

        intro_by_agent = {
            "chef": "Voici le panier d'ingredients pour preparer la recette, avec la preparation etape par etape.",
            "nutrition_generale": "Voici une proposition pratique basee uniquement sur les produits disponibles.",
            "nutrition_bebe": "Voici une proposition prudente basee uniquement sur les produits disponibles.",
            "general": "Voici les produits les plus pertinents que j'ai trouves.",
            "support": "Voici ce que je peux proposer.",
        }
        parts = [
            intro_by_agent.get(plan.agent, intro_by_agent["general"]),
            "",
            f"{count_note}:",
        ]
        if plan.product_display_mode == "recipe_ingredients":
            parts.append("Ingredients du panier:")
        parts.extend(product_lines)

        steps = self._merge_steps(rag.get("steps"), plan.steps, plan.guidance)
        if steps:
            title = "Recette et preparation:" if plan.agent == "chef" else "Conseils / prochaines etapes:"
            parts.extend(["", title])
            parts.extend(f"{index}. {step}" for index, step in enumerate(steps[:8], start=1))
        return "\n".join(parts)


class AssistantService:
    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, str]]] = {}
        self._session_state: dict[str, dict[str, Any]] = {}
        self._llm = LlmClient()
        self._router = RouterAgent(self._llm)
        self._responder = ResponseAgent(self._llm, ProductResolver(), SearchTranslatorAgent(self._llm))

    def chat(
        self,
        user_message: str,
        session_id: str | None,
        budget_tnd: float | None,
        cart_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        sid = session_id or str(uuid.uuid4())
        state = self._session_state.get(sid, {})
        if budget_tnd is not None:
            state["budget_tnd"] = budget_tnd

        plan = self._router.route(message=user_message, state=state, cart_items=cart_items)
        result = self._responder.handle(plan, state)

        self._remember(sid, user_message, result["assistant_message"], result["active_agent"])
        self._session_state[sid] = state

        return {
            "session_id": sid,
            **result,
        }

    def _remember(self, session_id: str, user_message: str, assistant_message: str, agent: str) -> None:
        thread = self._history.get(session_id, [])
        timestamp = str(time.time())
        thread.extend(
            [
                {"role": "user", "content": user_message, "agent": agent, "ts": timestamp},
                {"role": "assistant", "content": assistant_message, "agent": agent, "ts": timestamp},
            ]
        )
        self._history[session_id] = thread[-40:]


assistant_service = AssistantService()
