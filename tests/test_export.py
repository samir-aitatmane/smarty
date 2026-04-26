"""
tests/test_export.py — Tests unitaires des schémas AITONA
"""
import sys
sys.path.insert(0, "../backend")

import pytest
from datetime import date, datetime
from uuid import UUID
from services.aitona_schema import (
    ProjectInput, ProjectComputed, Task, TaskStatus, TaskCategory,
    RiskLevel, AitonaPayload, build_aitona_payload, tasks_from_matching,
    ReligiousCompatibility, HealthDetails, AdminDetails, InsuranceRecommendation
)


# ── Tests ProjectInput ────────────────────────────────────────────────────────

def test_project_input_creation():
    pi = ProjectInput(
        nationalite="FR",
        age=25,
        destination_country="TH",
        destination_name="Thaïlande",
        activity_type="tourisme",
        duree_sejour="2 semaines",
    )
    assert pi.nationalite == "FR"
    assert pi.destination_country == "TH"
    assert isinstance(pi.collected_at, datetime)

def test_project_input_defaults():
    pi = ProjectInput()
    assert pi.vaccins_faits == []
    assert pi.langues == []
    assert pi.raw_conversation == []
    assert pi.experience_internationale == False


# ── Tests Task ────────────────────────────────────────────────────────────────

def test_task_creation():
    t = Task(title="Faire la demande de visa", category=TaskCategory.ADMIN)
    assert t.title == "Faire la demande de visa"
    assert t.status == TaskStatus.TODO
    assert t.category == TaskCategory.ADMIN
    assert isinstance(t.id, UUID)

def test_task_status_enum():
    t = Task(title="Test", status=TaskStatus.DONE)
    assert t.status == TaskStatus.DONE

def test_task_category_enum():
    for cat in [TaskCategory.ADMIN, TaskCategory.HEALTH, TaskCategory.INSURANCE, TaskCategory.GENERAL]:
        t = Task(title="Test", category=cat)
        assert t.category == cat


# ── Tests AitonaPayload ───────────────────────────────────────────────────────

def test_payload_creation():
    pi = ProjectInput(nationalite="FR", destination_country="TH", destination_name="Thaïlande")
    pc = ProjectComputed(
        general_summary="Voyage en Thaïlande",
        risk_level=RiskLevel.MODERATE,
        risk_level_fr="Modéré",
        compatibility_score=75,
    )
    tasks = [Task(title="Vérifier le visa", category=TaskCategory.ADMIN)]

    payload = build_aitona_payload(
        user_id="user_123",
        session_id="session_456",
        project_input=pi,
        project_computed=pc,
        tasks=tasks,
    )

    assert payload.user_id == "user_123"
    assert payload.session_id == "session_456"
    assert len(payload.tasks) == 1
    assert isinstance(payload.idempotency_key, UUID)
    assert payload.contract is None
    assert payload.insureds == []

def test_payload_idempotency_unique():
    pi = ProjectInput()
    pc = ProjectComputed()
    p1 = build_aitona_payload("u1", "s1", pi, pc, [])
    p2 = build_aitona_payload("u1", "s1", pi, pc, [])
    assert p1.idempotency_key != p2.idempotency_key

def test_payload_json_serializable():
    pi = ProjectInput(nationalite="FR", destination_country="TH")
    pc = ProjectComputed(risk_level=RiskLevel.LOW)
    payload = build_aitona_payload("u", "s", pi, pc, [])
    json_data = payload.model_dump(mode="json")
    assert isinstance(json_data, dict)
    assert "idempotency_key" in json_data
    assert "project_input" in json_data
    assert "project_computed" in json_data


# ── Tests tasks_from_matching ─────────────────────────────────────────────────

def test_tasks_from_matching_empty():
    tasks = tasks_from_matching([])
    assert tasks == []

def test_tasks_from_matching_conversion():
    raw = [
        {"title": "Faire le visa", "description": "Visa requis", "category": "admin", "priority": "haute"},
        {"title": "Vaccin fièvre jaune", "category": "health", "priority": "haute"},
    ]
    tasks = tasks_from_matching(raw)
    assert len(tasks) == 2
    assert tasks[0].category == TaskCategory.ADMIN
    assert tasks[1].category == TaskCategory.HEALTH
    assert all(isinstance(t, Task) for t in tasks)
    assert all(t.status == TaskStatus.TODO for t in tasks)

def test_tasks_unknown_category():
    raw = [{"title": "Test", "category": "unknown_cat", "priority": "normale"}]
    tasks = tasks_from_matching(raw)
    assert tasks[0].category == TaskCategory.GENERAL


# ── Tests RiskLevel ───────────────────────────────────────────────────────────

def test_risk_level_values():
    assert RiskLevel.LOW == "low"
    assert RiskLevel.MODERATE == "moderate"
    assert RiskLevel.HIGH == "high"
    assert RiskLevel.UNKNOWN == "unknown"

def test_project_computed_defaults():
    pc = ProjectComputed()
    assert pc.risk_level == RiskLevel.UNKNOWN
    assert pc.compatibility_score == 0
    assert pc.personal_risks == []
    assert pc.warnings == []
    assert isinstance(pc.religious_compatibility, ReligiousCompatibility)
    assert isinstance(pc.health, HealthDetails)
    assert isinstance(pc.admin, AdminDetails)
    assert isinstance(pc.insurance, InsuranceRecommendation)