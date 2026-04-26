# Smarty — Agent IA Smart Starts

> Conseiller voyage intelligent pour la mobilité internationale.  
> Stack : LLaMA 3.3 (Azure) · FastAPI · Next.js · PostgreSQL · Azure Blob Storage

---

## Architecture

```
smarty/
├── backend/          FastAPI — logique métier, LLM, matching, export AITONA
├── frontend/         Next.js — interface chatbot
├── scraper/          Azure Container Jobs — mise à jour base de connaissances
├── knowledge/        JSON — données pays (modifiable sans toucher au code)
├── tests/            Tests unitaires et d'intégration (43 tests)
└── infra/            Scripts de déploiement Azure
```

---

## Démarrage rapide (local)

### Prérequis
- Python 3.10+
- Node.js 18+
- Compte Azure (voir Configuration Azure)

### 1. Cloner le repo

```bash
git clone https://github.com/votre-org/smarty.git
cd smarty
```

### 2. Configurer les variables d'environnement

```bash
cp backend/.env.example backend/.env
# Remplir les valeurs dans backend/.env
```

### 3. Installer les dépendances

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### 4. Lancer le projet

```bash
# Terminal 1 — Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

- Backend : http://localhost:8000
- Frontend : http://localhost:3000
- API Docs : http://localhost:8000/docs

---

## Configuration Azure

### Ressources nécessaires

| Ressource | Nom | Region |
|-----------|-----|--------|
| AI Foundry (LLaMA 3.3) | smarty-llama | Sweden Central |
| Blob Storage | smartystorage | Norway East |
| PostgreSQL | smarty-db | Norway East |
| Container Apps | smarty-backend | Norway East |

### Variables d'environnement

Voir `backend/.env.example` pour la liste complète.

| Variable | Description |
|----------|-------------|
| `AZURE_API_KEY` | Clé API Azure AI Foundry |
| `AZURE_ENDPOINT` | Endpoint LLaMA Azure |
| `AZURE_MODEL_NAME` | Nom du déploiement (ex: smarty-llama) |
| `AZURE_STORAGE_CONNECTION_STRING` | Chaîne de connexion Blob Storage |
| `DATABASE_URL` | URL PostgreSQL Azure |
| `SECRET_KEY` | Clé secrète API |

---

## Déploiement

### Backend (Azure Container Apps)

```bash
# Depuis la racine du projet
bash infra/deploy.sh
```

Le script :
1. Crée un Azure Container Registry
2. Build et push l'image Docker
3. Crée l'environnement Container Apps
4. Déploie l'application avec les variables d'environnement
5. Retourne l'URL de production

### Scraper (Azure Container Jobs)

```bash
bash infra/deploy_scraper.sh
```

Le scraper tourne automatiquement toutes les nuits à 2h00 UTC.

### Frontend (Vercel)

```bash
cd frontend
npx vercel --prod
```

Définir la variable d'environnement dans Vercel :
```
NEXT_PUBLIC_API_URL=https://votre-backend.azurecontainerapps.io
```

---

## Tests

```bash
# Lancer tous les tests
pytest -v

# Tests unitaires uniquement
pytest tests/test_matching.py tests/test_export.py -v

# Tests d'intégration uniquement
pytest tests/test_integration.py -v
```

**Résultat attendu : 43/43 tests passent**

---

## Migrer vers un compte Azure entreprise

**Aucune ligne de code à modifier.**

1. Créer les ressources Azure sur le nouveau compte
2. Mettre à jour les secrets dans Azure Container Apps (portail Azure)
3. Redéployer : `bash infra/deploy.sh`

Voir `Guide_Migration_Azure_Smarty.docx` pour les instructions détaillées.

---

## Mettre à jour la base de connaissances

Éditer `knowledge/knowledge_base.json` puis uploader sur Azure Blob :

```bash
az storage blob upload \
  --file knowledge/knowledge_base.json \
  --container-name smarty-knowledge \
  --name knowledge_base.json \
  --connection-string "<votre-connection-string>"
```

Ou lancer le scraper manuellement :

```bash
cd scraper
python update_knowledge.py
```

---

## Fonctionnalités

- **Chat intelligent** — conversation naturelle avec Smarty
- **Matching personnalisé** — pays/profil/activité avec score de compatibilité
- **Compatibilité religieuse** — analyse halal, mosquées, Ramadan, dress code
- **Upload CV et images** — extraction automatique du profil (OCR)
- **Vocal** — reconnaissance vocale + synthèse vocale
- **Historique** — conversations sauvegardées dans PostgreSQL
- **Export AITONA** — génération des 4 blocs JSON (projects, tasks, contracts, insureds)
- **Scraping automatique** — mise à jour nocturne de la base de connaissances

---

## Budget Azure estimé

| Ressource | Coût/mois |
|-----------|-----------|
| LLaMA 3.3 (tokens) | ~2-3$ |
| PostgreSQL B1ms | ~20$ |
| Blob Storage | ~1$ |
| Container Apps | ~5$ |
| Container Jobs (scraper) | ~0.10$ |
| **Total MVP** | **~28$/mois** |

---

## Licence

Confidentiel — Smart Starts © 2025