"""
scraper/scrape.py
Scrape les sites officiels pour mettre à jour la base de connaissances.
Sources : France Diplomatie, WHO, Brave Search API
Tourne toutes les nuits via Azure Container Jobs (cron).
"""

import asyncio
import httpx
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KNOWLEDGE_PATH = Path(__file__).parent.parent / "knowledge" / "knowledge_base.json"

BRAVE_API_KEY = ""  # Optionnel — Brave Search free tier (2000 req/mois)

# Sources officielles à scraper
SOURCES = {
    "FR": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/france/",
    "TH": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/thailande/",
    "JP": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/japon/",
    "MA": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/maroc/",
    "US": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/etats-unis/",
    "AU": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/australie/",
    "CA": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/canada/",
    "SN": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/senegal/",
    "TR": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/turquie/",
    "DE": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/allemagne/",
    "AE": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/emirats-arabes-unis/",
    "IN": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/inde/",
    "BR": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/bresil/",
    "ID": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/indonesie/",
    "KE": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/kenya/",
    "ES": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/espagne/",
    "SA": "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/arabie-saoudite/",
}

# Mapping des niveaux de vigilance France Diplomatie
VIGILANCE_MAP = {
    "vigilance normale": "low",
    "vigilance renforcée": "moderate",
    "déconseillé sauf raison impérative": "high",
    "formellement déconseillé": "high",
}


def load_knowledge_base() -> dict:
    """Charge la base de connaissances existante."""
    with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_knowledge_base(data: dict):
    """Sauvegarde la base de connaissances mise à jour."""
    data["_meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    data["_meta"]["scraper_last_run"] = datetime.now().isoformat()
    with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Base de connaissances sauvegardée : {KNOWLEDGE_PATH}")


async def scrape_diplomatie_country(client: httpx.AsyncClient, country_code: str, url: str) -> dict:
    """
    Scrape la page France Diplomatie pour un pays.
    Extrait le niveau de vigilance et les conseils principaux.
    """
    try:
        response = await client.get(url, timeout=15.0)
        if response.status_code != 200:
            logger.warning(f"Erreur HTTP {response.status_code} pour {country_code}")
            return {}

        text = response.text.lower()

        # Détecter le niveau de vigilance
        risk_level = "low"
        for keyword, level in VIGILANCE_MAP.items():
            if keyword in text:
                risk_level = level
                break

        logger.info(f"{country_code} — niveau de risque détecté : {risk_level}")
        return {
            "risk_level": risk_level,
            "source": "France Diplomatie",
            "scraped_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Erreur scraping {country_code} : {e}")
        return {}


async def search_brave(query: str) -> list[dict]:
    """
    Recherche des informations récentes via Brave Search API.
    Gratuit : 2000 requêtes/mois.
    """
    if not BRAVE_API_KEY:
        logger.info("Brave API key non configurée — skip")
        return []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
                params={"q": query, "count": 3, "lang": "fr"},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("web", {}).get("results", [])
    except Exception as e:
        logger.error(f"Erreur Brave Search : {e}")
    return []


async def scrape_who_alerts() -> list[str]:
    """
    Scrape les alertes sanitaires de l'OMS.
    Retourne une liste d'alertes en cours.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.who.int/emergencies/disease-outbreak-news",
                timeout=15.0,
            )
            if response.status_code == 200:
                text = response.text.lower()
                alerts = []
                diseases = ["choléra", "ebola", "mpox", "dengue", "paludisme", "covid", "fièvre jaune"]
                for disease in diseases:
                    if disease in text:
                        alerts.append(f"Alerte OMS active : {disease}")
                return alerts
    except Exception as e:
        logger.error(f"Erreur scraping WHO : {e}")
    return []


async def run_scraper():
    """Fonction principale — scrape toutes les sources et met à jour le JSON."""
    logger.info("=== Démarrage du scraper Smarty ===")
    start = datetime.now()

    kb = load_knowledge_base()
    updated_count = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": "Smarty-Bot/1.0 (Smart Starts travel advisor)"},
        follow_redirects=True,
    ) as client:

        # 1. Scraper France Diplomatie pour chaque pays
        for country_code, url in SOURCES.items():
            if country_code not in kb["countries"]:
                logger.info(f"Pays {country_code} pas encore dans la base — skip")
                continue

            scraped = await scrape_diplomatie_country(client, country_code, url)

            if scraped and "risk_level" in scraped:
                old_risk = kb["countries"][country_code].get("risk_level", "unknown")
                new_risk = scraped["risk_level"]

                if old_risk != new_risk:
                    logger.info(f"{country_code} : risque mis à jour {old_risk} → {new_risk}")
                    kb["countries"][country_code]["risk_level"] = new_risk
                    updated_count += 1

                kb["countries"][country_code]["last_scraped"] = scraped["scraped_at"]

            # Pause entre les requêtes pour être poli avec les serveurs
            await asyncio.sleep(2)

        # 2. Alertes OMS
        who_alerts = await scrape_who_alerts()
        if who_alerts:
            logger.info(f"Alertes OMS détectées : {who_alerts}")
            kb["_meta"]["who_alerts"] = who_alerts
            kb["_meta"]["who_alerts_updated"] = datetime.now().isoformat()

    # 3. Sauvegarder
    save_knowledge_base(kb)

    duration = (datetime.now() - start).seconds
    logger.info(f"=== Scraper terminé en {duration}s — {updated_count} pays mis à jour ===")


if __name__ == "__main__":
    asyncio.run(run_scraper())