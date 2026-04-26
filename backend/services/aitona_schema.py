"""
services/aitona_schema.py — Schémas de données AITONA
Ces modèles Pydantic garantissent que Smarty produit exactement
ce qu'AITONA attend, sans aucune transformation côté AITONA.
Smarty fait toute la logique, AITONA fait le stockage.
"""

from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional
from uuid import uuid4, UUID
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW      = "low"
    MODERATE = "moderate"
    HIGH     = "high"
    UNKNOWN  = "unknown"


class TaskStatus(str, Enum):
    TODO        = "todo"
    IN_PROGRESS = "in_progress"
    DONE        = "done"


class TaskCategory(str, Enum):
    ADMIN     = "admin"
    HEALTH    = "health"
    INSURANCE = "insurance"
    GENERAL   = "general"


class ActivityType(str, Enum):
    TOURISME           = "tourisme"
    STAGE              = "stage"
    TRAVAIL            = "travail"
    VOLONTARIAT        = "volontariat"
    EXPAT              = "expat"
    PELERINAGE         = "pelerinage"
    MISSION_HUMANITAIRE = "mission_humanitaire"
    ENSEIGNEMENT       = "enseignement"
    AUTRE              = "autre"


# ── Bloc 1 : projects.input ───────────────────────────────────────────────────

class ProjectInput(BaseModel):
    """
    Données brutes collectées pendant la conversation.
    Captura le contexte exact de la discussion.
    """
    # Identité utilisateur
    nationalite: str = Field("", description="Code ISO 3166 (ex: FR, DZ, MA)")
    age: int = Field(0, description="Âge de l'utilisateur")
    situation_familiale: str = Field("", description="seul, couple, famille_enfants")
    religion: str = Field("", description="islam, christianisme, judaisme, bouddhisme, autre, non_precise")

    # Voyage
    destination_country: str = Field("", description="Code ISO 3166 du pays de destination")
    destination_name: str = Field("", description="Nom complet du pays")
    activity_type: str = Field("", description="Type d'activité")
    duree_sejour: str = Field("", description="Durée du séjour (ex: 2 semaines, 3 mois)")
    budget_type: str = Field("", description="low, medium, high")

    # Santé
    conditions_medicales: str = Field("", description="Conditions médicales particulières")
    vaccins_faits: list[str] = Field(default_factory=list)

    # Profil pro
    niveau_etudes: str = Field("", description="Niveau d'études")
    domaine_competence: str = Field("", description="Domaine de compétence")
    experience_internationale: bool = False
    langues: list[str] = Field(default_factory=list)

    # Conversation brute
    raw_conversation: list[dict] = Field(
        default_factory=list,
        description="Historique complet de la conversation"
    )

    # CV uploadé
    cv_extrait: str = Field("", description="Contenu extrait du CV si uploadé")

    collected_at: datetime = Field(default_factory=datetime.utcnow)


# ── Bloc 2 : projects.computed ────────────────────────────────────────────────

class ReligiousCompatibility(BaseModel):
    """Compatibilité religieuse entre le profil et la destination."""
    compatible: bool = True
    score: int = Field(100, ge=0, le=100)
    conseils: list[str] = Field(default_factory=list)
    alertes: list[str] = Field(default_factory=list)


class HealthDetails(BaseModel):
    """Détails sanitaires pour la destination."""
    vaccines_required: list[str] = Field(default_factory=list)
    vaccines_recommended: list[str] = Field(default_factory=list)
    vaccines_missing: list[str] = Field(default_factory=list)
    health_risks: list[str] = Field(default_factory=list)
    eau_potable: bool = True
    emergency_contacts: list[str] = Field(default_factory=list)


class AdminDetails(BaseModel):
    """Détails administratifs pour la destination."""
    visa_required: bool = False
    visa_info: str = ""
    required_documents: list[str] = Field(default_factory=list)
    work_permit_required: bool = False


class InsuranceRecommendation(BaseModel):
    """Assurance recommandée pour ce profil."""
    product_id: str = ""
    product_name: str = ""
    coverage: list[str] = Field(default_factory=list)
    prix_indicatif: str = ""
    justification: str = ""


class ProjectComputed(BaseModel):
    """
    Données enrichies et structurées générées par Smarty.
    Résultat du matching intelligent.
    """
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    source_agent: str = "smarty-v1"

    # Résumé
    general_summary: str = ""
    compatibility_score: int = Field(0, ge=0, le=100)

    # Risque
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    risk_level_fr: str = ""
    personal_risks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Détails
    religious_compatibility: ReligiousCompatibility = Field(
        default_factory=ReligiousCompatibility
    )
    health: HealthDetails = Field(default_factory=HealthDetails)
    admin: AdminDetails = Field(default_factory=AdminDetails)
    insurance: InsuranceRecommendation = Field(
        default_factory=InsuranceRecommendation
    )


# ── Bloc 3 : tasks ────────────────────────────────────────────────────────────

class Task(BaseModel):
    """
    Action concrète à réaliser avant ou pendant le voyage.
    Générée automatiquement par le moteur de matching.
    """
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str = ""
    due_date: Optional[date] = None
    status: TaskStatus = TaskStatus.TODO
    category: TaskCategory = TaskCategory.GENERAL
    priority: str = "normale"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Bloc 4 : contracts & insureds ────────────────────────────────────────────

class Insured(BaseModel):
    """
    Données de l'assuré.
    RGPD : conservation limitée, données minimales.
    """
    id: UUID = Field(default_factory=uuid4)
    first_name: str
    last_name: str
    birth_date: date
    nationality: str = Field("", description="Code ISO 3166")
    email: str
    phone: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Contract(BaseModel):
    """Contrat d'assurance souscrit via Smart Starts."""
    id: UUID = Field(default_factory=uuid4)
    insurance_product: str
    insurance_product_id: str
    start_date: date
    end_date: date
    destination_country: str
    activity_type: str
    insured_ids: list[UUID] = Field(default_factory=list)
    prix_total: float = 0.0
    devise: str = "EUR"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Payload complet envoyé à AITONA ──────────────────────────────────────────

class AitonaPayload(BaseModel):
    """
    Objet final transmis à AITONA.
    Smarty produit, AITONA stocke.
    Zéro transformation nécessaire côté AITONA.
    """
    # Clé d'unicité — empêche les doublons côté AITONA
    idempotency_key: UUID = Field(
        default_factory=uuid4,
        description="Clé unique anti-doublon"
    )

    # Identification
    user_id: str
    session_id: str

    # Les 4 blocs de données
    project_input: ProjectInput
    project_computed: ProjectComputed
    tasks: list[Task] = Field(default_factory=list)

    # Optionnels (phase souscription)
    contract: Optional[Contract] = None
    insureds: list[Insured] = Field(default_factory=list)

    # Traçabilité
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_aitona_payload(
    user_id: str,
    session_id: str,
    project_input: ProjectInput,
    project_computed: ProjectComputed,
    tasks: list[Task],
    contract: Contract | None = None,
    insureds: list[Insured] | None = None,
) -> AitonaPayload:
    """
    Construit le payload AITONA complet prêt à être envoyé.
    Appelé par routers/export.py.
    """
    return AitonaPayload(
        user_id=user_id,
        session_id=session_id,
        project_input=project_input,
        project_computed=project_computed,
        tasks=tasks,
        contract=contract,
        insureds=insureds or [],
    )


def tasks_from_matching(matching_tasks: list[dict]) -> list[Task]:
    """
    Convertit les tâches générées par matching_engine en objets Task AITONA.
    """
    category_map = {
        "admin": TaskCategory.ADMIN,
        "health": TaskCategory.HEALTH,
        "insurance": TaskCategory.INSURANCE,
        "general": TaskCategory.GENERAL,
    }

    return [
        Task(
            title=t.get("title", ""),
            description=t.get("description", ""),
            category=category_map.get(t.get("category", "general"), TaskCategory.GENERAL),
            priority=t.get("priority", "normale"),
            status=TaskStatus.TODO,
        )
        for t in matching_tasks
    ]