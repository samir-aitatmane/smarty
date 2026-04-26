"""
scraper/update_knowledge.py
Met à jour le knowledge_base.json sur Azure Blob Storage
après que le scraper ait enrichi les données localement.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KNOWLEDGE_PATH = Path(__file__).parent.parent / "knowledge" / "knowledge_base.json"


async def upload_to_azure_blob():
    """
    Upload le knowledge_base.json vers Azure Blob Storage.
    Le backend recharge automatiquement le fichier au prochain appel.
    """
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    container_name = os.environ.get("AZURE_BLOB_CONTAINER", "smarty-knowledge")

    if not connection_string:
        logger.warning("AZURE_STORAGE_CONNECTION_STRING non configuré — upload ignoré")
        return False

    try:
        from azure.storage.blob import BlobServiceClient

        client = BlobServiceClient.from_connection_string(connection_string)
        container = client.get_container_client(container_name)

        with open(KNOWLEDGE_PATH, "rb") as f:
            container.upload_blob(
                name="knowledge_base.json",
                data=f,
                overwrite=True,
            )

        logger.info(f"knowledge_base.json uploadé sur Azure Blob ({container_name})")
        return True

    except Exception as e:
        logger.error(f"Erreur upload Azure Blob : {e}")
        return False


async def notify_backend_reload():
    """
    Notifie le backend de recharger la base de connaissances.
    Appelle l'endpoint /api/reload-knowledge si disponible.
    """
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{backend_url}/api/knowledge/reload",
                timeout=10.0,
            )
            if response.status_code == 200:
                logger.info("Backend notifié — base de connaissances rechargée")
            else:
                logger.warning(f"Backend reload status : {response.status_code}")
    except Exception as e:
        logger.info(f"Backend reload ignoré (normal en local) : {e}")


async def run_update():
    """
    Pipeline complet :
    1. Lance le scraper
    2. Upload sur Azure Blob
    3. Notifie le backend
    """
    logger.info("=== Mise à jour de la base de connaissances ===")

    # 1. Lancer le scraper
    from scrape import run_scraper
    await run_scraper()

    # 2. Upload sur Azure Blob
    uploaded = await upload_to_azure_blob()

    # 3. Notifier le backend
    if uploaded:
        await notify_backend_reload()

    logger.info("=== Mise à jour terminée ===")


if __name__ == "__main__":
    asyncio.run(run_update())