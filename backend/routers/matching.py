"""
routers/matching.py — Endpoint matching pays/profil
Expose le moteur de matching via l'API REST.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.matching_engine import UserProfile, run_matching, suggest_destinations
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Modèles de requête/réponse ────────────────────────────────────────────────

class MatchingRequest(BaseModel):
    # Identité
    nationalite: str = ""
    age: int = 0
    situation_familiale: str = ""
    religion: str = ""
    # Voyage
    destination: str = ""
    type_activite: str = ""
    duree_sejour: str = ""
    budget_type: str = ""
    # Santé
    vaccins_faits: list[str] = []
    conditions_medicales: str = ""
    # Pro
    domaine_competence: str = ""
    experience_internationale: bool = False


class SuggestRequest(BaseModel):
    nationalite: str = ""
    age: int = 0
    situation_familiale: str = ""
    religion: str = ""
    type_activite: str = ""
    budget_type: str = ""
    top_n: int = 5


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/")
async def match(req: MatchingRequest):
    """
    Lance le matching complet pour un profil et une destination.
    Retourne : niveau de risque, compatibilité religieuse,
    vaccins manquants, tâches, assurance recommandée, score.
    """
    try:
        profile = UserProfile(
            nationalite=req.nationalite,
            age=req.age,
            situation_familiale=req.situation_familiale,
            religion=req.religion,
            destination=req.destination,
            type_activite=req.type_activite,
            duree_sejour=req.duree_sejour,
            budget_type=req.budget_type,
            vaccins_faits=req.vaccins_faits,
            conditions_medicales=req.conditions_medicales,
            domaine_competence=req.domaine_competence,
            experience_internationale=req.experience_internationale,
        )

        result = run_matching(profile)

        if not result:
            raise HTTPException(status_code=404, detail="Destination introuvable")

        return {
            "country_code": result.country_code,
            "country_name": result.country_name,
            "risk_level": result.risk_level,
            "risk_level_fr": result.risk_level_fr,
            "compatibility_score": result.compatibility_score,
            "personal_risks": result.personal_risks,
            "warnings": result.warnings,
            "compatibilite_religieuse": result.compatibilite_religieuse,
            "insurance_recommended": result.insurance_recommended,
            "documents_requis": result.documents_requis,
            "vaccins_a_faire": result.vaccins_a_faire,
            "taches_suggerees": result.taches_suggerees,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur matching : {e}")
        raise HTTPException(status_code=500, detail="Erreur matching")


@router.post("/suggest")
async def suggest(req: SuggestRequest):
    """
    Suggère les meilleures destinations selon le profil.
    Utilisé quand l'utilisateur ne sait pas encore où aller.
    Retourne le top N des destinations les plus compatibles.
    """
    try:
        profile = UserProfile(
            nationalite=req.nationalite,
            age=req.age,
            situation_familiale=req.situation_familiale,
            religion=req.religion,
            type_activite=req.type_activite,
            budget_type=req.budget_type,
        )

        suggestions = suggest_destinations(profile, top_n=req.top_n)
        return {"suggestions": suggestions}

    except Exception as e:
        logger.error(f"Erreur suggest : {e}")
        raise HTTPException(status_code=500, detail="Erreur suggestion destinations")


@router.get("/countries")
async def get_countries():
    """
    Retourne la liste de tous les pays disponibles dans la base.
    Utilisé par le frontend pour afficher les destinations.
    """
    from services.knowledge import get_all_countries
    return {"countries": get_all_countries()}