"""
services/knowledge.py
Lit la base de connaissances depuis le JSON (MVP).
Plus tard : remplacer get_knowledge_base() par une requête PostgreSQL.
Le reste du code ne change pas.
"""

import json
import logging
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

KNOWLEDGE_PATH = Path(__file__).parent.parent.parent / "knowledge" / "knowledge_base.json"


@lru_cache()
def get_knowledge_base() -> dict:
    """
    Charge le knowledge_base.json en mémoire (une seule fois).
    Plus tard : remplacer par une requête PostgreSQL.
    """
    try:
        with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Base de connaissances chargée : {len(data['countries'])} pays")
        return data
    except FileNotFoundError:
        logger.error(f"knowledge_base.json introuvable : {KNOWLEDGE_PATH}")
        return {"countries": {}, "insurance_products": {}, "activity_risk_modifier": {}}
    except json.JSONDecodeError as e:
        logger.error(f"Erreur JSON : {e}")
        return {"countries": {}, "insurance_products": {}, "activity_risk_modifier": {}}


def get_country_context(country_code: str) -> dict | None:
    """
    Retourne les données d'un pays par son code ISO 3166.
    Retourne None si le pays n'est pas dans la base.
    """
    kb = get_knowledge_base()
    code = country_code.upper().strip()
    return kb["countries"].get(code, None)


def get_country_by_name(name: str) -> dict | None:
    """
    Cherche un pays par son nom (insensible à la casse).
    Utile quand l'utilisateur écrit le nom complet au lieu du code ISO.
    """
    kb = get_knowledge_base()
    name_lower = name.lower().strip()
    for code, data in kb["countries"].items():
        if data.get("name", "").lower() == name_lower:
            return {**data, "code": code}
    return None


def get_all_countries() -> list[dict]:
    """Retourne la liste de tous les pays disponibles."""
    kb = get_knowledge_base()
    return [
        {"code": code, "name": data.get("name"), "region": data.get("region"), "risk_level": data.get("risk_level")}
        for code, data in kb["countries"].items()
    ]


def get_insurance_products() -> dict:
    """Retourne tous les produits d'assurance disponibles."""
    return get_knowledge_base().get("insurance_products", {})


def get_insurance_recommendation(risk_level: str, activity: str, has_family: bool) -> dict:
    """
    Retourne le produit d'assurance recommandé selon :
    - Le niveau de risque du pays
    - L'activité prévue
    - Si voyage en famille
    """
    kb = get_knowledge_base()
    products = kb.get("insurance_products", {})
    modifiers = kb.get("activity_risk_modifier", {})

    activity_risk = modifiers.get(activity.lower(), "low")

    risk_priority = {"low": 1, "moderate": 2, "high": 3}
    final_risk = risk_level
    if risk_priority.get(activity_risk, 1) > risk_priority.get(risk_level, 1):
        final_risk = activity_risk

    if has_family:
        return products.get("smarty_famille", {})

    if final_risk == "high":
        return products.get("smarty_premium", {})
    elif final_risk == "moderate":
        return products.get("smarty_confort", {})
    else:
        return products.get("smarty_essentiel", {})


def build_llm_context(country_code: str | None, country_name: str | None) -> str:
    """
    Construit le contexte textuel à injecter dans le prompt LLaMA.
    Si le pays est dans la base -> contexte détaillé.
    Si le pays est hors base -> LLaMA utilise sa connaissance générale.
    """
    country_data = None

    if country_code:
        country_data = get_country_context(country_code)

    if not country_data and country_name:
        country_data = get_country_by_name(country_name)

    if not country_data:
        return (
            "Le pays demandé n'est pas dans la base de connaissances locale. "
            "Utilise ta connaissance générale pour répondre de façon précise et détaillée. "
            "Couvre : visa, santé, religion, sécurité, culture, budget, assurance recommandée."
        )

    name = country_data.get("name", "")
    risk = country_data.get("risk_level", "unknown")
    insurance = country_data.get("insurance_recommended", "smarty_essentiel")
    products = get_insurance_products()
    insurance_detail = products.get(insurance, {})

    context = f"""
=== DONNÉES OFFICIELLES POUR {name.upper()} ===

NIVEAU DE RISQUE GÉNÉRAL : {risk.upper()}

VISA :
{json.dumps(country_data.get("visa", {}), ensure_ascii=False, indent=2)}

SANTÉ :
{json.dumps(country_data.get("health", {}), ensure_ascii=False, indent=2)}

RELIGION & COMPATIBILITÉ :
{json.dumps(country_data.get("religion", {}), ensure_ascii=False, indent=2)}

SÉCURITÉ :
{json.dumps(country_data.get("security", {}), ensure_ascii=False, indent=2)}

CULTURE & LOIS :
{json.dumps(country_data.get("culture", {}), ensure_ascii=False, indent=2)}

BUDGET :
{json.dumps(country_data.get("budget", {}), ensure_ascii=False, indent=2)}

ACTIVITÉS AUTORISÉES :
{json.dumps(country_data.get("activities", {}), ensure_ascii=False, indent=2)}

FAMILLE & ENFANTS :
{json.dumps(country_data.get("famille", {}), ensure_ascii=False, indent=2)}

ASSURANCE RECOMMANDÉE : {insurance_detail.get("name", "")}
Couverture : {", ".join(insurance_detail.get("couverture", []))}
Prix indicatif : {insurance_detail.get("prix_indicatif", "")}

=== FIN DES DONNÉES OFFICIELLES ===
"""
    return context.strip()


def reload_knowledge_base():
    """
    Force le rechargement du JSON en mémoire.
    À appeler après une mise à jour par le scraper.
    """
    get_knowledge_base.cache_clear()
    logger.info("Base de connaissances rechargée")
    return get_knowledge_base()