"""
services/matching_engine.py
Moteur de matching intelligent.
Croise le profil utilisateur avec la base de connaissances
pour calculer le niveau de risque et les recommandations.
"""

import logging
from dataclasses import dataclass
from services.knowledge import (
    get_country_context,
    get_country_by_name,
    get_insurance_recommendation,
    build_llm_context,
    get_all_countries,
)

logger = logging.getLogger(__name__)


# ── Modèles de données ────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    """Profil complet de l'utilisateur collecté par la conversation."""
    # Identité
    nationalite: str = ""           # Code ISO 3166 (ex: FR, DZ, MA)
    age: int = 0
    situation_familiale: str = ""   # seul, couple, famille_enfants
    religion: str = ""              # islam, christianisme, judaisme, bouddhisme, hindouisme, autre, non_precise
    
    # Voyage
    destination: str = ""           # Code ISO ou nom du pays
    duree_sejour: str = ""          # ex: "2 semaines", "3 mois", "1 an"
    type_activite: str = ""         # tourisme, stage, travail, volontariat, expat, pelerinage
    budget_type: str = ""           # low, medium, high
    
    # Santé
    conditions_medicales: str = ""  # optionnel
    vaccins_faits: list = None
    
    # Profil pro
    niveau_etudes: str = ""
    domaine_competence: str = ""
    experience_internationale: bool = False
    
    # Document uploadé
    cv_extrait: str = ""            # Contenu extrait du CV si uploadé

    def __post_init__(self):
        if self.vaccins_faits is None:
            self.vaccins_faits = []

    @property
    def has_family(self) -> bool:
        return self.situation_familiale == "famille_enfants"

    @property
    def is_muslim(self) -> bool:
        return self.religion.lower() == "islam"


@dataclass
class MatchingResult:
    """Résultat complet du matching."""
    # Pays
    country_code: str
    country_name: str
    risk_level: str                 # low, moderate, high
    risk_level_fr: str              # Faible, Modéré, Élevé

    # Risques spécifiques au profil
    personal_risks: list            # Risques selon le profil de la personne
    warnings: list                  # Alertes importantes
    compatibilite_religieuse: dict  # Compatibilité avec la religion de l'utilisateur

    # Recommandations
    insurance_recommended: dict     # Produit d'assurance recommandé
    documents_requis: list          # Documents à préparer
    vaccins_a_faire: list           # Vaccins manquants
    taches_suggerees: list          # Actions concrètes à faire avant le départ

    # Contexte LLaMA
    llm_context: str                # Contexte injecté dans le prompt LLaMA

    # Score de compatibilité global (0-100)
    compatibility_score: int


# ── Fonctions principales ─────────────────────────────────────────────────────

def calculate_risk_level(base_risk: str, profile: UserProfile) -> str:
    """
    Ajuste le niveau de risque selon le profil utilisateur.
    Un pays modéré peut devenir élevé selon l'activité ou le profil.
    """
    risk_priority = {"low": 1, "moderate": 2, "high": 3}
    current = risk_priority.get(base_risk, 1)

    # Activités à risque élèvent le niveau
    high_risk_activities = ["mission_humanitaire", "travail_chantier", "sport_extreme", "recherche_terrain"]
    moderate_risk_activities = ["volontariat", "expat", "pelerinage"]

    if profile.type_activite in high_risk_activities:
        current = max(current, 3)
    elif profile.type_activite in moderate_risk_activities:
        current = max(current, 2)

    # Famille avec enfants → toujours au moins modéré
    if profile.has_family and current < 2:
        current = 2

    # Long séjour (> 3 mois) → élève le risque
    duree = profile.duree_sejour.lower()
    if any(x in duree for x in ["6 mois", "1 an", "2 ans", "longue durée"]):
        current = max(current, 2)

    levels = {1: "low", 2: "moderate", 3: "high"}
    return levels.get(current, "low")


def get_risk_label_fr(risk_level: str) -> str:
    labels = {"low": "Faible", "moderate": "Modéré", "high": "Élevé"}
    return labels.get(risk_level, "Inconnu")


def analyze_religious_compatibility(country_data: dict, profile: UserProfile) -> dict:
    """
    Analyse la compatibilité religieuse entre le profil et le pays.
    Retourne un dict avec score et conseils spécifiques.
    """
    religion_data = country_data.get("religion", {})
    result = {
        "compatible": True,
        "score": 100,
        "conseils": [],
        "alertes": []
    }

    if not profile.religion or profile.religion == "non_precise":
        return result

    if profile.is_muslim:
        # Vérifier disponibilité halal
        if not religion_data.get("muslim_friendly", False):
            result["score"] -= 30
            result["alertes"].append("Nourriture halal difficile à trouver")

        # Vérifier présence de mosquées
        if not religion_data.get("mosques", False):
            result["score"] -= 20
            result["alertes"].append("Peu ou pas de mosquées disponibles")

        # Alcool omniprésent
        alcool = religion_data.get("alcohol", "")
        if "interdit" not in alcool.lower() and "restreint" not in alcool.lower():
            result["conseils"].append("Alcool autorisé dans ce pays — zones sans alcool limitées")

        # Restrictions Ramadan
        ramadan = religion_data.get("ramadan", "")
        if ramadan:
            result["conseils"].append(f"Ramadan : {ramadan}")

        # Dress code
        dress = religion_data.get("dress_code_religieux", "")
        if dress:
            result["conseils"].append(f"Tenue : {dress}")

        # Pays très favorables aux musulmans
        if religion_data.get("halal_food") and "partout" in str(religion_data.get("halal_food", "")).lower():
            result["conseils"].append("Pays très favorable — alimentation halal partout disponible")

    # Restrictions légales importantes
    restrictions = religion_data.get("restrictions_religieuses", [])
    for r in restrictions:
        result["alertes"].append(r)

    if result["score"] < 50:
        result["compatible"] = False

    return result


def get_personal_risks(country_data: dict, profile: UserProfile) -> list:
    """
    Identifie les risques spécifiques au profil de l'utilisateur.
    Pas les risques généraux du pays, mais ceux qui concernent cette personne.
    """
    risks = []
    health = country_data.get("health", {})
    security = country_data.get("security", {})
    culture = country_data.get("culture", {})

    # Risques santé
    if health.get("eau_potable") is False:
        risks.append("Eau du robinet non potable — prévoir eau en bouteille")

    health_risks = health.get("risks", [])
    if health_risks:
        risks.append(f"Risques sanitaires : {', '.join(health_risks)}")

    # Famille avec enfants
    if profile.has_family:
        famille_data = country_data.get("famille", {})
        attention = famille_data.get("attention_enfants", [])
        for a in attention:
            risks.append(f"[ENFANTS] {a}")

    # Femme voyageant seule
    if profile.situation_familiale == "seul" and profile.age > 0:
        femmes_info = security.get("femmes", "")
        if femmes_info:
            risks.append(f"[FEMMES SEULES] {femmes_info}")

    # Lois importantes
    lois = culture.get("lois_importantes", [])
    for loi in lois:
        risks.append(f"[LOI] {loi}")

    # Arnaques courantes
    arnaques = security.get("arnaques_communes", [])
    if arnaques:
        risks.append(f"Arnaques fréquentes : {', '.join(arnaques)}")

    return risks


def get_missing_vaccines(country_data: dict, profile: UserProfile) -> list:
    """
    Calcule les vaccins manquants en comparant
    ce que le pays requiert/recommande et ce que l'utilisateur a déjà.
    """
    health = country_data.get("health", {})
    required = health.get("vaccines_required", [])
    recommended = health.get("vaccines_recommended", [])
    already_done = [v.lower().strip() for v in profile.vaccins_faits]

    missing = []
    for v in required:
        if not any(v.lower() in d or d in v.lower() for d in already_done):
            missing.append(f"[OBLIGATOIRE] {v}")

    for v in recommended:
        if not any(v.lower() in d or d in v.lower() for d in already_done):
            missing.append(f"[Recommandé] {v}")

    return missing


def generate_tasks(country_data: dict, profile: UserProfile, missing_vaccines: list) -> list:
    """
    Génère la liste des tâches concrètes à faire avant le départ.
    Ces tâches alimentent le bloc AITONA tasks[].
    """
    tasks = []
    visa_data = country_data.get("visa", {})
    health = country_data.get("health", {})
    nationalite = profile.nationalite.lower()

    # Visa
    visa_info = visa_data.get(nationalite, visa_data.get("france", ""))
    if visa_info and "sans visa" not in str(visa_info).lower():
        tasks.append({
            "title": "Faire la demande de visa",
            "description": f"Visa requis pour {country_data.get('name')} : {visa_info}",
            "category": "admin",
            "priority": "haute"
        })

    # Documents
    docs = visa_data.get("documents_requis", [])
    if docs:
        tasks.append({
            "title": "Préparer les documents de voyage",
            "description": f"Documents requis : {', '.join(docs)}",
            "category": "admin",
            "priority": "haute"
        })

    # Vaccins
    for vaccin in missing_vaccines:
        tasks.append({
            "title": f"Vaccination : {vaccin}",
            "description": "Consulter un médecin ou centre de vaccination internationale",
            "category": "health",
            "priority": "haute" if "OBLIGATOIRE" in vaccin else "normale"
        })

    # Assurance
    tasks.append({
        "title": "Souscrire à l'assurance voyage Smarty",
        "description": "Choisir le plan adapté à votre profil et destination",
        "category": "insurance",
        "priority": "haute"
    })

    # Paludisme
    if "Paludisme" in str(health.get("risks", [])):
        tasks.append({
            "title": "Consulter un médecin pour prophylaxie antipaludéenne",
            "description": "Traitement préventif contre le paludisme à commencer avant le départ",
            "category": "health",
            "priority": "haute"
        })

    # Famille
    if profile.has_family:
        tasks.append({
            "title": "Vérifier les vaccins des enfants",
            "description": "S'assurer que tous les enfants sont à jour dans leurs vaccinations",
            "category": "health",
            "priority": "haute"
        })

    return tasks


def calculate_compatibility_score(
    risk_level: str,
    religious_compatibility: dict,
    profile: UserProfile,
    country_data: dict
) -> int:
    """
    Calcule un score de compatibilité global entre 0 et 100.
    100 = destination parfaite pour ce profil.
    """
    score = 100

    # Déduction selon niveau de risque
    risk_deductions = {"low": 0, "moderate": -15, "high": -35}
    score += risk_deductions.get(risk_level, 0)

    # Déduction compatibilité religieuse
    religious_score = religious_compatibility.get("score", 100)
    if religious_score < 100:
        score -= (100 - religious_score) * 0.3

    # Famille → destinations à risque élevé moins compatibles
    if profile.has_family and risk_level == "high":
        score -= 20

    # Activité humanitaire/mission → risque assumé
    if profile.type_activite == "mission_humanitaire":
        score = max(score, 50)

    # Budget compatible ?
    budget_data = country_data.get("budget", {})
    if profile.budget_type == "low" and budget_data.get("low", ""):
        budget_str = budget_data.get("low", "0€/jour")
        try:
            daily_cost = int(''.join(filter(str.isdigit, budget_str.split("€")[0])))
            if daily_cost > 60:
                score -= 10
        except Exception:
            pass

    return max(0, min(100, int(score)))


def run_matching(profile: UserProfile) -> MatchingResult | None:
    """
    Fonction principale du moteur de matching.
    Prend un profil utilisateur et retourne un MatchingResult complet.
    """
    # Trouver les données du pays
    country_data = None
    country_code = profile.destination.upper() if len(profile.destination) == 2 else None

    if country_code:
        country_data = get_country_context(country_code)
    if not country_data:
        country_data = get_country_by_name(profile.destination)
        if country_data:
            country_code = country_data.get("code", profile.destination.upper())

    # Pays hors base → LLaMA gère avec sa connaissance générale
    if not country_data:
        logger.info(f"Pays hors base : {profile.destination} — LLaMA gère")
        return MatchingResult(
            country_code=profile.destination.upper(),
            country_name=profile.destination,
            risk_level="unknown",
            risk_level_fr="Inconnu",
            personal_risks=[],
            warnings=["Ce pays n'est pas encore dans notre base de données locale. Smarty utilisera sa connaissance générale."],
            compatibilite_religieuse={"compatible": True, "score": 100, "conseils": [], "alertes": []},
            insurance_recommended={},
            documents_requis=[],
            vaccins_a_faire=[],
            taches_suggerees=[],
            llm_context=build_llm_context(None, profile.destination),
            compatibility_score=50
        )

    # Calculer le niveau de risque ajusté au profil
    base_risk = country_data.get("risk_level", "low")
    adjusted_risk = calculate_risk_level(base_risk, profile)

    # Analyser la compatibilité religieuse
    religious_compat = analyze_religious_compatibility(country_data, profile)

    # Risques personnalisés
    personal_risks = get_personal_risks(country_data, profile)

    # Vaccins manquants
    missing_vaccines = get_missing_vaccines(country_data, profile)

    # Tâches à faire
    tasks = generate_tasks(country_data, profile, missing_vaccines)

    # Assurance recommandée
    insurance = get_insurance_recommendation(
        adjusted_risk,
        profile.type_activite,
        profile.has_family
    )

    # Score de compatibilité
    score = calculate_compatibility_score(adjusted_risk, religious_compat, profile, country_data)

    # Documents requis
    visa_data = country_data.get("visa", {})
    docs = visa_data.get("documents_requis", [])

    # Warnings importants
    warnings = []
    if adjusted_risk == "high":
        warnings.append("Destination à risque élevé — assurance premium fortement recommandée")
    if religious_compat.get("alertes"):
        warnings.extend(religious_compat["alertes"])
    zones_danger = country_data.get("security", {}).get("zones_dangereuses", [])
    if zones_danger:
        warnings.append(f"Zones dangereuses : {', '.join(zones_danger)}")

    # Contexte LLaMA
    llm_context = build_llm_context(country_code, country_data.get("name"))

    return MatchingResult(
        country_code=country_code,
        country_name=country_data.get("name", ""),
        risk_level=adjusted_risk,
        risk_level_fr=get_risk_label_fr(adjusted_risk),
        personal_risks=personal_risks,
        warnings=warnings,
        compatibilite_religieuse=religious_compat,
        insurance_recommended=insurance,
        documents_requis=docs,
        vaccins_a_faire=missing_vaccines,
        taches_suggerees=tasks,
        llm_context=llm_context,
        compatibility_score=score
    )


def suggest_destinations(profile: UserProfile, top_n: int = 5) -> list[dict]:
    """
    Suggère les meilleures destinations selon le profil
    quand l'utilisateur ne sait pas encore où aller.
    """
    all_countries = get_all_countries()
    results = []

    for country in all_countries:
        temp_profile = UserProfile(
            nationalite=profile.nationalite,
            age=profile.age,
            situation_familiale=profile.situation_familiale,
            religion=profile.religion,
            destination=country["code"],
            type_activite=profile.type_activite,
            budget_type=profile.budget_type,
        )
        result = run_matching(temp_profile)
        if result:
            results.append({
                "code": country["code"],
                "name": country["name"],
                "region": country["region"],
                "risk_level": result.risk_level,
                "risk_level_fr": result.risk_level_fr,
                "compatibility_score": result.compatibility_score,
                "insurance": result.insurance_recommended.get("name", ""),
            })

    # Trier par score de compatibilité décroissant
    results.sort(key=lambda x: x["compatibility_score"], reverse=True)
    return results[:top_n]