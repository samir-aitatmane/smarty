"""
routers/conversations.py — Endpoints gestion de l'historique des conversations
Sauvegarde, charge et liste les conversations depuis PostgreSQL.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_pool
import logging
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Modèles ───────────────────────────────────────────────────────────────────

class SaveMessageRequest(BaseModel):
    session_id: str
    user_id: str = "anonymous"
    role: str           # "user" ou "assistant"
    content: str
    message_type: str = "text"

class SaveConversationRequest(BaseModel):
    session_id: str
    user_id: str = "anonymous"
    title: str = "Nouvelle conversation"
    messages: list[dict] = []


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def get_conversations(user_id: str = "anonymous", limit: int = 20):
    """
    Retourne la liste des conversations d'un utilisateur.
    Triées par date de mise à jour (plus récente en premier).
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    c.id,
                    c.session_id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id = $1
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT $2
            """, user_id, limit)

        return {
            "conversations": [
                {
                    "id": str(r["id"]),
                    "session_id": r["session_id"],
                    "title": r["title"],
                    "message_count": r["message_count"],
                    "created_at": r["created_at"].isoformat(),
                    "updated_at": r["updated_at"].isoformat(),
                }
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"Erreur get_conversations : {e}")
        raise HTTPException(status_code=500, detail="Erreur chargement historique")


@router.get("/{session_id}/messages")
async def get_messages(session_id: str):
    """
    Retourne tous les messages d'une conversation.
    Utilisé pour restaurer une conversation depuis l'historique.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Vérifier que la conversation existe
            conv = await conn.fetchrow(
                "SELECT id FROM conversations WHERE session_id = $1", session_id
            )
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation introuvable")

            rows = await conn.fetch("""
                SELECT role, content, message_type, created_at
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
            """, conv["id"])

        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "type": r["message_type"],
                    "created_at": r["created_at"].isoformat(),
                }
                for r in rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_messages : {e}")
        raise HTTPException(status_code=500, detail="Erreur chargement messages")


@router.post("/save")
async def save_conversation(req: SaveConversationRequest):
    """
    Sauvegarde ou met à jour une conversation complète.
    Appelé automatiquement après chaque échange.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():

                # Générer un titre depuis le premier message utilisateur
                title = req.title
                if req.messages:
                    first_user = next(
                        (m["content"] for m in req.messages if m.get("role") == "user"), None
                    )
                    if first_user:
                        title = first_user[:60] + ("..." if len(first_user) > 60 else "")

                # Créer ou mettre à jour la conversation
                conv = await conn.fetchrow("""
                    INSERT INTO conversations (session_id, user_id, title)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (session_id) DO UPDATE
                    SET title = $3, updated_at = NOW()
                    RETURNING id
                """, req.session_id, req.user_id, title)

                conv_id = conv["id"]

                # Supprimer les anciens messages et réinsérer
                await conn.execute(
                    "DELETE FROM messages WHERE conversation_id = $1", conv_id
                )

                if req.messages:
                    await conn.executemany("""
                        INSERT INTO messages (conversation_id, role, content, message_type)
                        VALUES ($1, $2, $3, $4)
                    """, [
                        (conv_id, m.get("role", "user"), m.get("content", ""), m.get("type", "text"))
                        for m in req.messages
                        if m.get("role") in ("user", "assistant") and m.get("content")
                    ])

        return {"success": True, "session_id": req.session_id, "title": title}

    except Exception as e:
        logger.error(f"Erreur save_conversation : {e}")
        raise HTTPException(status_code=500, detail="Erreur sauvegarde conversation")


@router.delete("/{session_id}")
async def delete_conversation(session_id: str):
    """Supprime une conversation et tous ses messages."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM conversations WHERE session_id = $1", session_id
            )
        return {"success": True}
    except Exception as e:
        logger.error(f"Erreur delete_conversation : {e}")
        raise HTTPException(status_code=500, detail="Erreur suppression")