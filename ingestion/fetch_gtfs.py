"""
Ingestion du fichier GTFS Île-de-France.
Télécharge le ZIP, extrait les fichiers et charge en base PostgreSQL (schema raw).
"""

import logging
import zipfile
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

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
    response = requests.get(url, timeout=120)
    response.raise_for_status()

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

    Args:
        dest_dir: Répertoire contenant les fichiers .txt extraits.
        engine: Connexion SQLAlchemy vers PostgreSQL.
    """
    for filename in GTFS_FILES:
        filepath = dest_dir / filename
        if not filepath.exists():
            logger.warning("Fichier introuvable, skip : %s", filepath)
            continue

        table_name = f"gtfs_{filepath.stem}"  # ex: gtfs_stops
        logger.info("Chargement de %s → raw.%s", filename, table_name)

        df = pd.read_csv(filepath, dtype=str, low_memory=False)
        logger.info("  %d lignes, %d colonnes", len(df), len(df.columns))

        df.to_sql(
            name=table_name,
            con=engine,
            schema="raw",
            if_exists="replace",
            index=False,
        )
        logger.info("  ✓ Chargé en base")


def main() -> None:
    """Point d'entrée principal du script d'ingestion GTFS."""
    # Connexion PostgreSQL (variables d'env à configurer)
    import os

    db_url = os.environ.get("DATABASE_URL", "postgresql://gpe:gpe@localhost:5432/gpe")
    engine = create_engine(db_url)

    zip_path = download_gtfs(GTFS_URL, RAW_DIR)
    extract_gtfs(zip_path, RAW_DIR)
    load_to_postgres(RAW_DIR, engine)
    logger.info("✅ Ingestion GTFS terminée")


if __name__ == "__main__":
    main()
