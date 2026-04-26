"""
database.py — Connexion PostgreSQL et création des tables
Utilise asyncpg pour les requêtes asynchrones.
"""

import asyncpg
import logging
from config import settings

logger = logging.getLogger(__name__)

_pool = None


async def get_pool():
    """Retourne le pool de connexions (singleton)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
        )
        logger.info("Pool PostgreSQL créé")
    return _pool


async def init_db():
    """
    Crée les tables si elles n'existent pas.
    Appelé au démarrage de l'application.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id  TEXT NOT NULL UNIQUE,
                user_id     TEXT NOT NULL DEFAULT 'anonymous',
                title       TEXT NOT NULL DEFAULT 'Nouvelle conversation',
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content         TEXT NOT NULL,
                message_type    TEXT DEFAULT 'text',
                created_at      TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_user_id
            ON conversations(user_id, updated_at DESC);
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
            ON messages(conversation_id, created_at ASC);
        """)

    logger.info("Tables PostgreSQL initialisées")


async def close_db():
    """Ferme le pool de connexions."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None