"""
routers/export.py — Endpoint export AITONA
Génère le payload complet et l'envoie au système AITONA.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from services.aitona_schema import (
    ProjectInput, ProjectComputed, RiskLevel,
    ReligiousCompatibility, HealthDetails, AdminDetails,
    InsuranceRecommendation, Task, TaskCategory, TaskStatus,
    build_aitona_payload, tasks_from_matching
)
from services.matching_engine import UserProfile, run_matching
from config import settings
import httpx
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Modèles de requête ────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    session_id: str
    user_id: str = "anonymous"

    # Profil complet collecté par la conversation
    nationalite: str = ""
    age: int = 0
    situation_familiale: str = ""
    religion: str = ""
    destination_country: str = ""
    destination_name: str = ""
    type_activite: str = ""
    duree_sejour: str = ""
    budget_type: str = ""
    vaccins_faits: list[str] = []
    conditions_medicales: str = ""
    domaine_competence: str = ""
    experience_internationale: bool = False
    langues: list[str] = []

    # Historique conversation
    raw_conversation: list[dict] = []

    # CV extrait si uploadé
    cv_extrait: str = ""


# ── Endpoint principal ────────────────────────────────────────────────────────

@router.post("/")
async def export_to_aitona(req: ExportRequest):
    """
    Génère le payload AITONA complet et l'envoie via webhook.
    Étapes :
    1. Lance le matching sur le profil
    2. Construit les 4 blocs JSON AITONA
    3. Envoie au webhook AITONA (ou simule si pas configuré)
    4. Retourne le payload généré
    """
    try:
        # ── Étape 1 : Matching ────────────────────────────────────────────────
        profile = UserProfile(
            nationalite=req.nationalite,
            age=req.age,
            situation_familiale=req.situation_familiale,
            religion=req.religion,
            destination=req.destination_country or req.destination_name,
            type_activite=req.type_activite,
            duree_sejour=req.duree_sejour,
            budget_type=req.budget_type,
            vaccins_faits=req.vaccins_faits,
            conditions_medicales=req.conditions_medicales,
            domaine_competence=req.domaine_competence,
            experience_internationale=req.experience_internationale,
        )

        matching = run_matching(profile)

        # ── Étape 2 : Construire ProjectInput ─────────────────────────────────
        project_input = ProjectInput(
            nationalite=req.nationalite,
            age=req.age,
            situation_familiale=req.situation_familiale,
            religion=req.religion,
            destination_country=req.destination_country,
            destination_name=req.destination_name,
            activity_type=req.type_activite,
            duree_sejour=req.duree_sejour,
            budget_type=req.budget_type,
            conditions_medicales=req.conditions_medicales,
            vaccins_faits=req.vaccins_faits,
            domaine_competence=req.domaine_competence,
            experience_internationale=req.experience_internationale,
            langues=req.langues,
            raw_conversation=req.raw_conversation,
            cv_extrait=req.cv_extrait,
        )

        # ── Étape 3 : Construire ProjectComputed ──────────────────────────────
        insurance = matching.insurance_recommended if matching else {}
        religious = matching.compatibilite_religieuse if matching else {}

        project_computed = ProjectComputed(
            general_summary=_build_summary(req, matching),
            compatibility_score=matching.compatibility_score if matching else 0,
            risk_level=RiskLevel(matching.risk_level) if matching and matching.risk_level != "unknown" else RiskLevel.UNKNOWN,
            risk_level_fr=matching.risk_level_fr if matching else "",
            personal_risks=matching.personal_risks if matching else [],
            warnings=matching.warnings if matching else [],
            religious_compatibility=ReligiousCompatibility(
                compatible=religious.get("compatible", True),
                score=religious.get("score", 100),
                conseils=religious.get("conseils", []),
                alertes=religious.get("alertes", []),
            ),
            health=HealthDetails(
                vaccines_missing=matching.vaccins_a_faire if matching else [],
            ),
            admin=AdminDetails(
                required_documents=matching.documents_requis if matching else [],
            ),
            insurance=InsuranceRecommendation(
                product_id=insurance.get("product_id", ""),
                product_name=insurance.get("name", ""),
                coverage=insurance.get("couverture", []),
                prix_indicatif=insurance.get("prix_indicatif", ""),
                justification=f"Recommandé pour un profil {matching.risk_level_fr if matching else ''} vers {req.destination_name}",
            ),
        )

        # ── Étape 4 : Construire les Tasks ────────────────────────────────────
        tasks = tasks_from_matching(
            matching.taches_suggerees if matching else []
        )

        # ── Étape 5 : Assembler le payload AITONA ─────────────────────────────
        payload = build_aitona_payload(
            user_id=req.user_id,
            session_id=req.session_id,
            project_input=project_input,
            project_computed=project_computed,
            tasks=tasks,
        )

        # ── Étape 6 : Envoyer à AITONA ────────────────────────────────────────
        aitona_response = await _send_to_aitona(payload.model_dump(mode="json"))

        return {
            "success": True,
            "idempotency_key": str(payload.idempotency_key),
            "payload": payload.model_dump(mode="json"),
            "aitona_response": aitona_response,
        }

    except Exception as e:
        logger.error(f"Erreur export AITONA : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur export : {str(e)}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_summary(req: ExportRequest, matching) -> str:
    """Construit le résumé général du projet de voyage."""
    parts = []
    if req.destination_name:
        parts.append(f"Voyage vers {req.destination_name}")
    if req.type_activite:
        parts.append(f"pour {req.type_activite}")
    if req.duree_sejour:
        parts.append(f"durée {req.duree_sejour}")
    if matching:
        parts.append(f"risque {matching.risk_level_fr}")
        parts.append(f"score compatibilité {matching.compatibility_score}/100")
    return " — ".join(parts) if parts else "Projet de voyage Smart Starts"


async def _send_to_aitona(payload: dict) -> dict:
    """
    Envoie le payload au webhook AITONA.
    Si AITONA_WEBHOOK_URL n'est pas configuré → simulation (mode mock).
    """
    webhook_url = settings.aitona_webhook_url

    # Mode mock si pas de webhook configuré
    if not webhook_url:
        logger.info("Mode mock AITONA — webhook non configuré")
        return {
            "mode": "mock",
            "status": "simulated",
            "message": "Payload AITONA généré avec succès (mode simulation)",
            "idempotency_key": payload.get("idempotency_key"),
        }

    # Envoi réel au webhook AITONA
    try:
        headers = {"Content-Type": "application/json"}
        if settings.aitona_api_key:
            headers["Authorization"] = f"Bearer {settings.aitona_api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return {"mode": "live", "status": "sent", "http_status": response.status_code}

    except httpx.TimeoutException:
        logger.error("Timeout webhook AITONA")
        return {"mode": "live", "status": "timeout", "error": "AITONA timeout"}
    except Exception as e:
        logger.error(f"Erreur webhook AITONA : {e}")
        return {"mode": "live", "status": "error", "error": str(e)}