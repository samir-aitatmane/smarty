"""
tests/conftest.py — Configuration globale des tests pytest
"""
import sys
import os
import pytest

# Ajouter le backend au path Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

# Variables d'environnement pour les tests (pas besoin de vraies clés)
os.environ.setdefault("AZURE_API_KEY", "test_key")
os.environ.setdefault("AZURE_ENDPOINT", "https://test.azure.com")
os.environ.setdefault("AZURE_MODEL_NAME", "test-model")
os.environ.setdefault("AZURE_API_VERSION", "2024-05-01-preview")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net")
os.environ.setdefault("AZURE_BLOB_CONTAINER", "test-container")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ENVIRONMENT", "test")