"""
tests/test_matching.py — Tests unitaires du moteur de matching
"""
import sys
sys.path.insert(0, "../backend")

import pytest
from services.matching_engine import (
    UserProfile, run_matching, calculate_risk_level,
    analyze_religious_compatibility, get_missing_vaccines,
    suggest_destinations
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def profile_muslim_france():
    return UserProfile(
        nationalite="FR", age=25, situation_familiale="seul",
        religion="islam", destination="TH", type_activite="tourisme",
        duree_sejour="2 semaines", budget_type="medium", vaccins_faits=[]
    )

@pytest.fixture
def profile_famille_senegal():
    return UserProfile(
        nationalite="FR", age=35, situation_familiale="famille_enfants",
        religion="", destination="SN", type_activite="volontariat",
        duree_sejour="1 mois", budget_type="low", vaccins_faits=["Hépatite A"]
    )

@pytest.fixture
def profile_pays_hors_base():
    return UserProfile(
        nationalite="FR", age=28, situation_familiale="couple",
        religion="", destination="VN", type_activite="tourisme",
        duree_sejour="3 semaines", budget_type="medium",
    )


# ── Tests calculate_risk_level ─────────────────────────────────────────────────

def test_risk_low_tourisme():
    p = UserProfile(destination="JP", type_activite="tourisme", situation_familiale="seul")
    assert calculate_risk_level("low", p) == "low"

def test_risk_elevated_by_activity():
    p = UserProfile(destination="JP", type_activite="mission_humanitaire", situation_familiale="seul")
    assert calculate_risk_level("low", p) == "high"

def test_risk_elevated_by_family():
    p = UserProfile(destination="JP", type_activite="tourisme", situation_familiale="famille_enfants")
    assert calculate_risk_level("low", p) == "moderate"

def test_risk_long_stay():
    p = UserProfile(destination="TH", type_activite="expat", situation_familiale="seul", duree_sejour="1 an")
    assert calculate_risk_level("low", p) == "moderate"


# ── Tests religious compatibility ─────────────────────────────────────────────

def test_muslim_thailand(profile_muslim_france):
    from services.knowledge import get_country_context
    data = get_country_context("TH")
    result = analyze_religious_compatibility(data, profile_muslim_france)
    assert "compatible" in result
    assert 0 <= result["score"] <= 100

def test_muslim_saudi_perfect():
    p = UserProfile(religion="islam", destination="SA")
    from services.knowledge import get_country_context
    data = get_country_context("SA")
    result = analyze_religious_compatibility(data, p)
    assert result["score"] == 100
    assert result["compatible"] == True

def test_no_religion_neutral():
    p = UserProfile(religion="", destination="TH")
    from services.knowledge import get_country_context
    data = get_country_context("TH")
    result = analyze_religious_compatibility(data, p)
    assert result["score"] == 100


# ── Tests vaccins ─────────────────────────────────────────────────────────────

def test_missing_vaccine_senegal():
    p = UserProfile(vaccins_faits=[])
    from services.knowledge import get_country_context
    data = get_country_context("SN")
    missing = get_missing_vaccines(data, p)
    assert any("Fièvre jaune" in v for v in missing)
    assert any("OBLIGATOIRE" in v for v in missing)

def test_already_vaccinated():
    p = UserProfile(vaccins_faits=["fièvre jaune", "hépatite a"])
    from services.knowledge import get_country_context
    data = get_country_context("SN")
    missing = get_missing_vaccines(data, p)
    assert not any("Fièvre jaune" in v for v in missing)

def test_no_required_vaccines_japan():
    p = UserProfile(vaccins_faits=[])
    from services.knowledge import get_country_context
    data = get_country_context("JP")
    missing = get_missing_vaccines(data, p)
    assert not any("OBLIGATOIRE" in v for v in missing)


# ── Tests run_matching ────────────────────────────────────────────────────────

def test_matching_basic(profile_muslim_france):
    result = run_matching(profile_muslim_france)
    assert result is not None
    assert result.country_code == "TH"
    assert result.country_name == "Thaïlande"
    assert result.risk_level in ("low", "moderate", "high")
    assert 0 <= result.compatibility_score <= 100

def test_matching_famille_high_risk(profile_famille_senegal):
    result = run_matching(profile_famille_senegal)
    assert result is not None
    assert result.risk_level in ("moderate", "high")
    assert len(result.vaccins_a_faire) > 0
    assert len(result.taches_suggerees) > 0

def test_matching_unknown_country(profile_pays_hors_base):
    result = run_matching(profile_pays_hors_base)
    assert result is not None
    assert result.risk_level == "unknown"
    assert len(result.warnings) > 0

def test_matching_insurance_not_none(profile_muslim_france):
    result = run_matching(profile_muslim_france)
    assert result.insurance_recommended is not None
    assert isinstance(result.insurance_recommended, dict)

def test_matching_tasks_generated(profile_famille_senegal):
    result = run_matching(profile_famille_senegal)
    assert len(result.taches_suggerees) >= 2
    cats = [t.get("category") for t in result.taches_suggerees]
    assert "health" in cats or "admin" in cats


# ── Tests suggest_destinations ────────────────────────────────────────────────

def test_suggest_returns_list():
    p = UserProfile(nationalite="FR", religion="islam", type_activite="tourisme",
                    budget_type="medium", situation_familiale="seul")
    suggestions = suggest_destinations(p, top_n=5)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 5

def test_suggest_sorted_by_score():
    p = UserProfile(nationalite="FR", religion="islam", type_activite="tourisme",
                    budget_type="medium", situation_familiale="seul")
    suggestions = suggest_destinations(p, top_n=5)
    scores = [s["compatibility_score"] for s in suggestions]
    assert scores == sorted(scores, reverse=True)