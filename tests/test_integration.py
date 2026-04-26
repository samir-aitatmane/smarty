"""
tests/test_integration.py — Tests d'intégration des endpoints API
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock


def make_llm_mock():
    """Crée un mock synchrone correct pour AzureOpenAI."""
    mock_message = MagicMock()
    mock_message.content = "Bonjour ! Je suis Smarty."

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def make_pool_mock():
    """Crée un mock correct pour asyncpg pool."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value={"id": "123e4567-e89b-12d3-a456-426614174000"})    
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.executemany = AsyncMock(return_value=None)

    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
    mock_transaction.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=mock_transaction)

    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_acquire)

    return mock_pool


@pytest.fixture
def app():
    with patch("services.llm._client", make_llm_mock()), \
         patch("database._pool", make_pool_mock()):
        from main import app
        yield app


# ── Tests Health Check ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root_endpoint(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "Smarty" in response.json()["message"]


# ── Tests Chat ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_basic(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/", json={
            "messages": [{"role": "user", "content": "Bonjour Smarty"}],
            "session_id": "test_session_001"
        })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["session_id"] == "test_session_001"


@pytest.mark.asyncio
async def test_chat_with_country_context(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/", json={
            "messages": [{"role": "user", "content": "Je veux aller en Thaïlande"}],
            "session_id": "test_session_003",
            "detected_country_code": "TH",
            "detected_country_name": "Thaïlande"
        })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_empty_messages(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat/", json={
            "messages": [],
            "session_id": "test_session_002"
        })
    assert response.status_code in (200, 422, 503)


# ── Tests Matching ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_matching_basic(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/matching/", json={
            "nationalite": "FR", "age": 25, "situation_familiale": "seul",
            "religion": "islam", "destination": "TH",
            "type_activite": "tourisme", "duree_sejour": "2 semaines",
            "budget_type": "medium", "vaccins_faits": []
        })
    assert response.status_code == 200
    data = response.json()
    assert "risk_level" in data
    assert "compatibility_score" in data
    assert "insurance_recommended" in data
    assert "taches_suggerees" in data


@pytest.mark.asyncio
async def test_matching_unknown_country(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/matching/", json={
            "nationalite": "FR", "destination": "ZZ", "type_activite": "tourisme"
        })
    assert response.status_code == 200
    assert response.json()["risk_level"] == "unknown"


@pytest.mark.asyncio
async def test_suggest_destinations(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/matching/suggest", json={
            "nationalite": "FR", "religion": "islam",
            "type_activite": "tourisme", "budget_type": "medium", "top_n": 3
        })
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) <= 3


@pytest.mark.asyncio
async def test_get_countries(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/matching/countries")
    assert response.status_code == 200
    data = response.json()
    assert "countries" in data
    assert len(data["countries"]) > 0


# ── Tests Export AITONA ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_aitona_mock(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/export/", json={
            "session_id": "test_export_001", "user_id": "test_user",
            "nationalite": "FR", "age": 25,
            "destination_country": "TH", "destination_name": "Thaïlande",
            "type_activite": "tourisme", "duree_sejour": "2 semaines",
            "budget_type": "medium",
            "raw_conversation": [{"role": "user", "content": "Je veux aller en Thaïlande"}]
        })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert "idempotency_key" in data
    assert "payload" in data
    payload = data["payload"]
    assert "project_input" in payload
    assert "project_computed" in payload
    assert "tasks" in payload


@pytest.mark.asyncio
async def test_export_payload_4_blocs(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/export/", json={
            "session_id": "test_export_002", "user_id": "test_user",
            "destination_country": "SN", "destination_name": "Sénégal",
            "type_activite": "volontariat", "situation_familiale": "famille_enfants"
        })
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert "project_input" in payload
    assert "project_computed" in payload
    assert "tasks" in payload
    assert isinstance(payload["tasks"], list)


# ── Tests Conversations ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_conversations_empty(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/conversations/?user_id=test_user")
    assert response.status_code == 200
    data = response.json()
    assert "conversations" in data
    assert isinstance(data["conversations"], list)


@pytest.mark.asyncio
async def test_save_conversation(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/conversations/save", json={
            "session_id": "test_conv_001",
            "user_id": "test_user",
            "title": "Test conversation",
            "messages": [
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour ! Je suis Smarty."}
            ]
        })
    assert response.status_code == 200
    assert response.json()["success"] == True