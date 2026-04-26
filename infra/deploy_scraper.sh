#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# infra/deploy_scraper.sh — Déploiement du scraper comme Azure Container Job
# Tourne toutes les nuits à 2h00 UTC
# ─────────────────────────────────────────────────────────────────────────────

set -e

RESOURCE_GROUP="smarty-rg"
ACR_NAME="smartyregistry"
ENV_NAME="smarty-env"
JOB_NAME="smarty-scraper"

# Charger les variables
if [ -f "backend/.env" ]; then
    export $(grep -v '^#' backend/.env | xargs)
fi

ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)

echo "🕷️  Déploiement du scraper..."

# Build image scraper
az acr build \
    --registry $ACR_NAME \
    --image smarty-scraper:latest \
    --file scraper/Dockerfile \
    scraper/

# Créer le Container Job (cron toutes les nuits à 2h00 UTC)
az containerapp job create \
    --name $JOB_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $ENV_NAME \
    --trigger-type "Schedule" \
    --cron-expression "0 2 * * *" \
    --image $ACR_LOGIN_SERVER/smarty-scraper:latest \
    --registry-server $ACR_LOGIN_SERVER \
    --registry-username $ACR_NAME \
    --registry-password $ACR_PASSWORD \
    --cpu 0.25 \
    --memory 0.5Gi \
    --env-vars \
        AZURE_STORAGE_CONNECTION_STRING="$AZURE_STORAGE_CONNECTION_STRING" \
        AZURE_BLOB_CONTAINER="$AZURE_BLOB_CONTAINER" \
        BACKEND_URL="https://$(az containerapp show --name smarty-backend --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn --output tsv)" \
    2>/dev/null || echo "Job déjà existant — mise à jour..."

echo "✅ Scraper déployé — tourne toutes les nuits à 2h00 UTC"