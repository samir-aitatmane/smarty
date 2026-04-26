"""
main.py — Point d'entrée de l'API Smarty
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import init_db, close_db
import logging

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Smarty API",
    description="Agent IA Smart Starts — Mobilité internationale",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Événements démarrage/arrêt ────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("Smarty API démarrée")

@app.on_event("shutdown")
async def shutdown():
    await close_db()

# ── Routers ───────────────────────────────────────────────────────────────────
from routers import chat, matching, export, conversations

app.include_router(chat.router,          prefix="/api/chat",          tags=["Chat"])
app.include_router(matching.router,      prefix="/api/matching",      tags=["Matching"])
app.include_router(export.router,        prefix="/api/export",        tags=["Export AITONA"])
app.include_router(conversations.router, prefix="/api/conversations",  tags=["Historique"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "smarty-api", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"message": "Smarty API — Smart Starts", "docs": "/docs"}