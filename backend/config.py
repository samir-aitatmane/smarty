"""
config.py — Configuration centralisée de Smarty
Toutes les variables d'environnement passent par ici.
Le reste du code importe uniquement `settings`, jamais os.environ directement.
Quand le client migre vers son compte Azure entreprise :
  -> il met à jour ses secrets Azure
  -> ce fichier ne change pas
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):

    # ── Azure AI Foundry — LLaMA 3.3 ─────────────────────────────────────────
    azure_api_key: str
    azure_endpoint: str
    azure_model_name: str = "smarty-llama"
    azure_api_version: str = "2024-05-01-preview"

    # ── Azure Blob Storage — base de connaissances ────────────────────────────
    azure_storage_connection_string: str
    azure_blob_container: str = "smarty-knowledge"

    # ── Base de données PostgreSQL ────────────────────────────────────────────
    database_url: str

    # ── Sécurité ──────────────────────────────────────────────────────────────
    secret_key: str
    allowed_origins: str = "http://localhost:3000"

    # ── Application ───────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"

    # ── AITONA ────────────────────────────────────────────────────────────────
    aitona_webhook_url: str = ""
    aitona_api_key: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Retourne une instance unique de Settings (singleton).
    Usage dans le reste du code :
        from config import settings
        print(settings.azure_endpoint)
    """
    return Settings()


# Raccourci pour les imports simples
settings = get_settings()