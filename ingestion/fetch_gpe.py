"""
Téléchargement et chargement des gares du Grand Paris Express en base raw.

Source : Société du Grand Paris via data.gouv.fr — format GeoJSON
Contenu : gares des lignes 15, 16, 17, 18 avec coordonnées GPS et métadonnées
"""

import logging
import os
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# GeoJSON officiel des gares GPE — Société du Grand Paris
GPE_GARES_URL = (
    "https://data.iledefrance-mobilites.fr/api/explore/v2.1/"
    "catalog/datasets/emplacement-des-gares-idf/exports/geojson"
)

# Lignes du Grand Paris Express (hors prolongements RER existants)
LIGNES_GPE = {"15", "16", "17", "18"}


def download_gpe(url: str) -> dict[str, Any]:
    """Télécharge le GeoJSON des gares GPE depuis data.gouv.fr.

    Args:
        url: URL du fichier GeoJSON des gares GPE.

    Returns:
        Contenu GeoJSON parsé en dictionnaire Python.

    Raises:
        requests.HTTPError: Si le téléchargement échoue.
    """
    logger.info(f"Téléchargement gares GPE depuis {url}")

    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
    except requests.HTTPError as e:
        logger.error(f"Échec du téléchargement : {e}")
        raise

    logger.info("Téléchargement OK")
    return response.json()


def parse_gpe(geojson: dict[str, Any]) -> pd.DataFrame:
    """Extrait les gares GPE depuis le GeoJSON vers DataFrame plat.
    => parse_gpe teste plusieurs noms possibles (nom_gare, name, libelle)

    GeoJSON spec standard :
    { "type": "FeatureCollection", "features": [...] }

    On extrait properties et coordonnées depuis geometry.

    Args:
        geojson: Dictionnaire GeoJSON des gares GPE.

    Returns:
        DataFrame avec une ligne par gare, colonnes : nom, ligne, longitude, latitude.

    Raises:
        KeyError: Si la structure GeoJSON ne correspond pas au format attendu.
        ValueError: Si aucune gare GPE n'est trouvée après filtrage.
    """
    features = geojson.get("features", [])
    logger.info(f"{len(features)} features trouvées dans le GeoJSON")

    rows = []
    for feature in features:
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        # Les coordonnées GeoJSON sont [longitude, latitude] (ordre GeoJSON standard)
        coords = geometry.get("coordinates", [None, None])

        rows.append(
            {
                "nom_gare": props.get("nom_gare")
                or props.get("name")
                or props.get("libelle"),
                "ligne": props.get("ligne")
                or props.get("line")
                or props.get("indice_lig"),
                "longitude": coords[0],
                "latitude": coords[1],
                "mise_en_service": props.get(
                    "mise_en_service"
                ),  # année d'ouverture prévue
                "statut": props.get("statut")
                or props.get("etat"),  # en travaux, ouvert, etc.
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("Aucune gare trouvée — vérifier la source")

    # Supprime les lignes sans coordonnées (données incomplètes)
    df = df.dropna(subset=["longitude", "latitude"])

    logger.info(f"{len(df)} gares chargées")
    return df


def load_to_postgres(df: pd.DataFrame, engine: Engine) -> None:
    """Charge les gares GPE dans raw.gpe_gares.

    Stratégie replace : on écrase à chaque run car les données GPE
    évoluent (ouvertures de gares, modifications de tracé).

    Args:
        df: DataFrame des gares GPE à charger.
        engine: Connexion SQLAlchemy vers Postgres.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Si le chargement échoue.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))

    logger.info(f"Chargement raw.gpe_gares — {len(df)} gares")

    try:
        df.to_sql(
            name="gpe_gares",
            con=engine,
            schema="raw",
            if_exists="replace",
            index=False,
        )
        logger.info("raw.gpe_gares OK")

    except Exception as e:
        logger.error(f"Échec chargement raw.gpe_gares : {e}")
        raise


def run(database_url: str) -> None:
    """Point d'entrée principal du script d'ingestion GPE.

    Args:
        database_url: URL de connexion Postgres (format SQLAlchemy).
            Exemple : postgresql://user:password@localhost:5432/gpe
    """
    logger.info("=== Début ingestion GPE ===")

    engine = create_engine(database_url)
    geojson = download_gpe(GPE_GARES_URL)
    df = parse_gpe(geojson)
    load_to_postgres(df, engine)

    logger.info("=== Ingestion GPE terminée ===")


if __name__ == "__main__":
    db_url = os.environ["DATABASE_URL"]
    run(db_url)
