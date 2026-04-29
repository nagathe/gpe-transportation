"""
Module d'ingestion des données GTFS Île-de-France.
Télécharge, extrait et charge les stops et stop_times en base PostgreSQL.
"""

import logging
import os
import zipfile
from io import BytesIO

import pandas as pd
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

GTFS_URL = (
    "https://data.ile-de-france-mobilites.fr/api/explore/v2.1/"
    "catalog/datasets/idfm-gtfs/exports/csv"
)
GTFS_FILES = ["stops.txt", "stop_times.txt", "trips.txt", "routes.txt"]


def download_gtfs(url: str = GTFS_URL, timeout: int = 30) -> bytes:
    """
    Télécharge le fichier GTFS zippé depuis l'URL donnée.

    Args:
        url: URL du fichier GTFS.
        timeout: Timeout HTTP en secondes.

    Returns:
        Contenu binaire du fichier zip.

    Raises:
        requests.HTTPError: Si la réponse HTTP est une erreur.
    """
    logger.info("Téléchargement GTFS depuis %s", url)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    logger.info("Téléchargement terminé (%d bytes)", len(response.content))
    return response.content


def extract_gtfs(zip_bytes: bytes) -> dict[str, pd.DataFrame]:
    """
    Extrait les fichiers depuis un zip GTFS en mémoire.

    Returns:
        Dict avec clé = nom du fichier sans .txt, valeur = DataFrame.

    Raises:
        zipfile.BadZipFile: Si le contenu n'est pas un zip valide.
    """
    result: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        for filename in GTFS_FILES:
            if filename in z.namelist():
                with z.open(filename) as f:
                    key = filename.replace(".txt", "")
                    result[key] = pd.read_csv(f, dtype=str)
                    logger.info("%s : %d lignes extraites", filename, len(result[key]))
            else:
                logger.warning("%s absent du zip", filename)
    return result


def parse_stops(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie et type le DataFrame des arrêts GTFS.

    Args:
        df: DataFrame brut issu de stops.txt.

    Returns:
        DataFrame nettoyé avec stop_id, stop_name, stop_lat, stop_lon.
    """
    cols = ["stop_id", "stop_name", "stop_lat", "stop_lon"]
    df = df[cols].dropna(subset=["stop_id", "stop_lat", "stop_lon"])
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    df = df.dropna(subset=["stop_lat", "stop_lon"])
    logger.info("%d arrêts valides après nettoyage", len(df))
    return df.reset_index(drop=True)


def load_to_postgres(df: pd.DataFrame, table: str, engine: Engine) -> None:
    """
    Charge un DataFrame dans PostgreSQL (schéma raw).

    Args:
        df: DataFrame à charger.
        table: Nom de la table cible.
        engine: Connexion SQLAlchemy.
    """
    logger.info("Chargement de %d lignes dans raw.%s", len(df), table)
    df.to_sql(table, engine, schema="raw", if_exists="replace", index=False)
    logger.info("Chargement terminé pour raw.%s", table)


def main(database_url: str) -> None:
    """Point d'entrée principal du script d'ingestion GTFS.

    Args:
        database_url: URL de connexion Postgres (format SQLAlchemy).
    """
    logger.info("=== Début ingestion GTFS ===")

    engine = create_engine(database_url)

    # Créer le schéma raw s'il n'existe pas
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.commit()

    # Télécharger et traiter GTFS
    zip_bytes = download_gtfs()
    dfs = extract_gtfs(zip_bytes)

    # Charger stops
    stops = parse_stops(dfs["stops"])
    load_to_postgres(stops, "gtfs_stops", engine)

    # Charger stop_times
    if "stop_times" in dfs:
        load_to_postgres(dfs["stop_times"], "gtfs_stop_times", engine)

    # Charger trips
    if "trips" in dfs:
        load_to_postgres(dfs["trips"], "gtfs_trips", engine)

    # Charger routes
    if "routes" in dfs:
        load_to_postgres(dfs["routes"], "gtfs_routes", engine)

    logger.info("=== Ingestion GTFS terminée ===")


if __name__ == "__main__":
    db_url = os.environ["DATABASE_URL"]
    main(db_url)
