#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# infra/deploy.sh — Déploiement Smarty sur Azure Container Apps
# Usage : bash infra/deploy.sh
# Prérequis : az CLI installé + connecté (az login)
# ─────────────────────────────────────────────────────────────────────────────

set -e  # Arrêter si une commande échoue

# ── Variables — modifier selon votre environnement ───────────────────────────
RESOURCE_GROUP="smarty-rg"
LOCATION="norwayeast"
ACR_NAME="smartyregistry"           # Azure Container Registry
APP_NAME="smarty-backend"           # Nom de l'app Container Apps
ENV_NAME="smarty-env"               # Container Apps Environment
IMAGE_NAME="smarty-backend"
IMAGE_TAG="latest"

# Charger les variables du .env
if [ -f "backend/.env" ]; then
    export $(grep -v '^#' backend/.env | xargs)
    echo "✅ Variables .env chargées"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  Déploiement Smarty sur Azure"
echo "═══════════════════════════════════════════"
echo ""

# ── Étape 1 : Créer Azure Container Registry ─────────────────────────────────
echo "📦 Étape 1 — Création du Container Registry..."
az acr create \
    --resource-group $RESOURCE_GROUP \
    --name $ACR_NAME \
    --sku Basic \
    --admin-enabled true \
    2>/dev/null || echo "ACR déjà existant — OK"

# Récupérer les credentials ACR
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)

echo "✅ ACR : $ACR_LOGIN_SERVER"

# ── Étape 2 : Build et push de l'image Docker ────────────────────────────────
echo ""
echo "🐳 Étape 2 — Build et push de l'image Docker..."

# Copier knowledge_base.json dans le backend pour le build
cp -r knowledge backend/knowledge

az acr build \
    --registry $ACR_NAME \
    --image $IMAGE_NAME:$IMAGE_TAG \
    --file backend/Dockerfile \
    backend/

# Nettoyer
rm -rf backend/knowledge

echo "✅ Image pushée : $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG"

# ── Étape 3 : Créer l'environnement Container Apps ───────────────────────────
echo ""
echo "☁️  Étape 3 — Création de l'environnement Container Apps..."
az containerapp env create \
    --name $ENV_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    2>/dev/null || echo "Environnement déjà existant — OK"

echo "✅ Environnement : $ENV_NAME"

# ── Étape 4 : Déployer l'application ─────────────────────────────────────────
echo ""
echo "🚀 Étape 4 — Déploiement de l'application..."

az containerapp create \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $ENV_NAME \
    --image $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG \
    --registry-server $ACR_LOGIN_SERVER \
    --registry-username $ACR_NAME \
    --registry-password $ACR_PASSWORD \
    --target-port 8000 \
    --ingress external \
    --min-replicas 0 \
    --max-replicas 3 \
    --cpu 0.5 \
    --memory 1.0Gi \
    --env-vars \
        AZURE_API_KEY="$AZURE_API_KEY" \
        AZURE_ENDPOINT="$AZURE_ENDPOINT" \
        AZURE_MODEL_NAME="$AZURE_MODEL_NAME" \
        AZURE_API_VERSION="$AZURE_API_VERSION" \
        AZURE_STORAGE_CONNECTION_STRING="$AZURE_STORAGE_CONNECTION_STRING" \
        AZURE_BLOB_CONTAINER="$AZURE_BLOB_CONTAINER" \
        DATABASE_URL="$DATABASE_URL" \
        SECRET_KEY="$SECRET_KEY" \
        ALLOWED_ORIGINS="$ALLOWED_ORIGINS" \
        ENVIRONMENT="production" \
        LOG_LEVEL="INFO" \
    2>/dev/null || \
az containerapp update \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --image $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG

# ── Étape 5 : Récupérer l'URL ─────────────────────────────────────────────────
echo ""
echo "🔗 Étape 5 — Récupération de l'URL..."
APP_URL=$(az containerapp show \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query properties.configuration.ingress.fqdn \
    --output tsv)

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ DÉPLOIEMENT TERMINÉ !"
echo "═══════════════════════════════════════════"
echo ""
echo "  URL Backend : https://$APP_URL"
echo "  Health Check : https://$APP_URL/health"
echo "  API Docs : https://$APP_URL/docs"
echo ""
echo "  Mettre à jour NEXT_PUBLIC_API_URL dans Vercel :"
echo "  https://$APP_URL"
echo ""