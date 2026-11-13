"""Ingestion du fichier GTFS Île-de-France.

Télécharge le ZIP, extrait les fichiers et charge en base PostgreSQL.
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

# Seul stops.txt est utilisé par dbt (stg_gtfs_stops). routes, trips et
# stop_times (~740 Mo décompressés, dont 695 Mo pour stop_times) ne sont pas
# chargés : décision #21, option A.
GTFS_FILES = ["stops.txt"]

# Colonnes de raw.gtfs_stops dans db/init.sql. Les autres colonnes de
# stops.txt (zone_id, stop_url, level_id, platform_code, stop_access) ne
# sont pas chargées.
STOPS_COLUMNS = [
    "stop_id",
    "stop_code",
    "stop_name",
    "stop_desc",
    "stop_lat",
    "stop_lon",
    "location_type",
    "parent_station",
    "stop_timezone",
    "wheelchair_boarding",
]


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
    size_mb = zip_path.stat().st_size / 1e6
    logger.info("Fichier sauvegardé : %s (%.1f MB)", zip_path, size_mb)
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


def prepare_stops(filepath: Path) -> pd.DataFrame:
    """Lit stops.txt et l'aligne sur le DDL de raw.gtfs_stops.

    Garde uniquement les colonnes de STOPS_COLUMNS, dans cet ordre (une
    colonne absente du fichier est ajoutée vide). Les identifiants restent
    en texte ('0001' ne devient pas 1) ; coordonnées et codes sont
    convertis en nombres.

    Args:
        filepath: Chemin vers stops.txt.

    Returns:
        DataFrame prêt à être inséré dans raw.gtfs_stops.

    Raises:
        ValueError: Si la colonne stop_id est absente.
    """
    df = pd.read_csv(filepath, dtype=str)
    if "stop_id" not in df.columns:
        raise ValueError(f"Colonne stop_id absente de {filepath}")

    df = df.reindex(columns=STOPS_COLUMNS)
    for col in ["stop_lat", "stop_lon"]:
        df[col] = pd.to_numeric(df[col])
    for col in ["location_type", "wheelchair_boarding"]:
        df[col] = pd.to_numeric(df[col]).astype("Int64")
    return df


def load_to_postgres(dest_dir: Path, engine: Engine) -> None:
    """Charge stops.txt dans raw.gtfs_stops (TRUNCATE + INSERT).

    La table n'est jamais supprimée : elle garde sa clé primaire et ses
    types (db/init.sql), et les vues dbt qui en dépendent restent valides.

    Args:
        dest_dir: Répertoire contenant stops.txt.
        engine: Connexion SQLAlchemy vers PostgreSQL.

    Raises:
        FileNotFoundError: Si stops.txt est absent.
        RuntimeError: Si raw.gtfs_stops n'existe pas (make db-init).
    """
    filepath = dest_dir / "stops.txt"
    if not filepath.exists():
        raise FileNotFoundError(f"Fichier GTFS introuvable : {filepath}")

    df = prepare_stops(filepath)
    logger.info("Chargement de %d arrêts dans raw.gtfs_stops", len(df))

    with engine.begin() as conn:
        if not engine.dialect.has_table(conn, "gtfs_stops", schema="raw"):
            raise RuntimeError(
                "Table raw.gtfs_stops absente : lancer make db-init d'abord"
            )
        conn.execute(text("TRUNCATE TABLE raw.gtfs_stops"))

    df.to_sql(
        name="gtfs_stops",
        con=engine,
        schema="raw",
        if_exists="append",
        index=False,
    )
    logger.info("Chargement terminé")


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
