"""
Ingestion du fichier GTFS Île-de-France.
Télécharge le ZIP, extrait les fichiers et charge en base PostgreSQL (schema raw).
"""

import logging
import os
import zipfile
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GTFS_URL = "https://eu.ftp.opendatasoft.com/stif/GTFS/IDFM-gtfs.zip"
RAW_DIR = Path("data/raw/gtfs")

# Fichiers GTFS qu'on veut charger (on garde l'essentiel)
GTFS_FILES = ["stops.txt", "routes.txt", "trips.txt", "stop_times.txt"]


def download_gtfs(url: str, dest_dir: Path) -> Path:
    """Télécharge le ZIP GTFS et le sauvegarde localement.

    Args:
        url: URL du fichier ZIP GTFS.
        dest_dir: Répertoire de destination.

    Returns:
        Chemin vers le fichier ZIP téléchargé.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "IDFM-gtfs.zip"

    logger.info("Téléchargement du GTFS depuis %s", url)
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
    except requests.HTTPError as e:
        logger.error("Échec du téléchargement GTFS : %s", e)
        raise
    except requests.ConnectionError as e:
        logger.error("Erreur réseau GTFS : %s", e)
        raise

    zip_path.write_bytes(response.content)
    logger.info(
        "Fichier sauvegardé : %s (%.1f MB)", zip_path, zip_path.stat().st_size / 1e6
    )
    return zip_path


def extract_gtfs(zip_path: Path, dest_dir: Path) -> None:
    """Extrait les fichiers GTFS utiles du ZIP.

    Args:
        zip_path: Chemin vers le fichier ZIP.
        dest_dir: Répertoire d'extraction.
    """
    logger.info("Extraction du ZIP dans %s", dest_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for filename in GTFS_FILES:
            if filename in zf.namelist():
                zf.extract(filename, dest_dir)
                logger.info("Extrait : %s", filename)
            else:
                logger.warning("Fichier absent du ZIP : %s", filename)


def load_to_postgres(dest_dir: Path, engine: Engine) -> None:
    """Charge les fichiers GTFS en base dans le schema raw.

    Supprime les vues dépendantes avant le rechargement pour éviter les
    conflits de contrainte (DROP VIEW ... CASCADE).

    Args:
        dest_dir: Répertoire contenant les fichiers .txt extraits.
        engine: Connexion SQLAlchemy vers PostgreSQL.
    """
    for filename in GTFS_FILES:
        filepath = dest_dir / filename
        if not filepath.exists():
            logger.warning("Fichier introuvable, skip : %s", filepath)
            continue

        table_name = f"gtfs_{filepath.stem}"
        logger.info("Chargement de %s → raw.%s", filename, table_name)

        try:
            # Supprime les vues dépendantes avant de recréer la table raw
            with engine.begin() as conn:
                conn.execute(
                    text(f"DROP VIEW IF EXISTS staging.stg_{table_name} CASCADE;")
                )
                logger.info("Vues dépendantes nettoyées pour raw.%s", table_name)

            # Charge les données
            df = pd.read_csv(filepath, dtype=str, low_memory=False)
            df.to_sql(
                name=table_name,
                con=engine,
                schema="raw",
                if_exists="replace",
                index=False,
            )
            logger.info("  Chargé en base : %d lignes", len(df))
        except Exception as e:
            logger.error("Échec chargement raw.%s : %s", table_name, e)
            raise


def main() -> None:
    """Point d'entrée principal du script d'ingestion GTFS."""
    logger.info("=== Début ingestion GTFS ===")

    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url)

    zip_path = download_gtfs(GTFS_URL, RAW_DIR)
    extract_gtfs(zip_path, RAW_DIR)
    load_to_postgres(RAW_DIR, engine)

    logger.info("=== Ingestion GTFS terminée ===")


if __name__ == "__main__":
    main()
