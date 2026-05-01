"""
Ingestion des gares GPE (Grand Paris Express) depuis le shapefile.

Source: data.gouv.fr — Point de localisation des gares GPE (Lignes 15, 16, 17, 18)
Format: Shapefile
Projection: Lambert 93 (EPSG:2154) → à convertir en WGS84 (EPSG:4326)
"""

import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Configuration logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)


def download_gpe_shapefile(url: str, output_path: Path) -> Path:
    """
    Télécharge le ZIP contenant le shapefile GPE.

    Args:
        url: URL du fichier ZIP sur data.gouv.fr
        output_path: Chemin local où sauvegarder

    Returns:
        Path: Chemin du fichier ZIP téléchargé
    """
    import urllib.request

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Téléchargement GPE shapefile depuis {url}")
    urllib.request.urlretrieve(url, output_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Fichier sauvegardé : {output_path} ({size_mb:.1f} MB)")

    return output_path


def extract_shapefile(zip_path: Path, extract_dir: Path) -> Path:
    """
    Dézipe le shapefile.

    Args:
        zip_path: Chemin du ZIP
        extract_dir: Dossier de destination

    Returns:
        Path: Dossier contenant les fichiers extraits
    """
    extract_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Extraction du ZIP dans {extract_dir}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    # Lister les fichiers extraits
    shp_files = list(extract_dir.glob("*.shp"))
    logger.info(f"Fichiers extraits : {[f.name for f in extract_dir.glob('*')]}")

    if not shp_files:
        raise FileNotFoundError(f"Aucun fichier .shp trouvé dans {extract_dir}")

    return extract_dir


def load_and_transform_shapefile(shp_dir: Path) -> gpd.GeoDataFrame:
    """
    Charge le shapefile et le transforme en WGS84.

    Args:
        shp_dir: Dossier contenant les fichiers du shapefile

    Returns:
        GeoDataFrame: Gares GPE en WGS84 (EPSG:4326)
    """
    # Trouver le fichier .shp
    shp_files = list(shp_dir.glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"Aucun .shp trouvé dans {shp_dir}")

    shp_path = shp_files[0]
    logger.info(f"Lecture du shapefile : {shp_path}")

    gdf = gpd.read_file(shp_path)

    logger.info(f"Chargé : {len(gdf)} gares")
    logger.info(f"Colonnes : {gdf.columns.tolist()}")
    logger.info(f"CRS original : {gdf.crs}")

    # Convertir Lambert 93 → WGS84
    if gdf.crs != "EPSG:4326":
        logger.info(f"Conversion {gdf.crs} → EPSG:4326")
        gdf = gdf.to_crs("EPSG:4326")

    # Extraire lat/lon de la géométrie
    gdf["longitude"] = gdf.geometry.x
    gdf["latitude"] = gdf.geometry.y

    # Renommer colonnes pour cohérence
    gdf = gdf.rename(
        columns={
            "LIBELLE": "nom_gare",
            "LIGNE": "ligne_gpe",
            "CONNEX": "interconnexion",
            "CODE": "code_gare",
        }
    )

    logger.info(
        f"Transform OK : {gdf[['code_gare', 'nom_gare', 'ligne_gpe', 'latitude', 'longitude']].head()}"
    )

    return gdf


def load_to_postgres(
    gdf: gpd.GeoDataFrame, engine: Engine, table_name: str = "raw.gpe_gares_shapefile"
) -> None:
    """
    Charge le GeoDataFrame dans PostgreSQL + PostGIS.

    Args:
        gdf: GeoDataFrame des gares GPE
        engine: Connexion SQLAlchemy à PostgreSQL
        table_name: Nom de la table de destination
    """
    logger.info(f"Chargement {table_name} — {len(gdf)} gares")

    # PostGIS : utiliser to_postgis() avec if_exists='replace'
    gdf.to_postgis(
        name=table_name.split(".")[-1],
        con=engine,
        schema=table_name.split(".")[0],
        if_exists="replace",
        index=False,
        chunksize=100,
    )

    logger.info(f"✓ {table_name} chargée")


def main():
    """Pipeline complet d'ingestion GPE shapefile."""

    logger.info("=== Début ingestion GPE Shapefile ===")

    # Paramètres
    url = "https://static.data.gouv.fr/resources/point-de-localisation-des-gares-de-la-ligne-15-sud-et-ligne-16/20161219-110430/GPE_GARE_LOCALISATION.zip"

    data_dir = Path(__file__).parent.parent / "data" / "raw" / "gpe"
    zip_path = data_dir / "gpe_gares.zip"
    extract_dir = data_dir / "gpe_shapefile_extracted"

    # Télécharger
    download_gpe_shapefile(url, zip_path)

    # Extraire
    extract_shapefile(zip_path, extract_dir)

    # Charger et transformer
    gdf = load_and_transform_shapefile(extract_dir)

    # Connexion PostgreSQL
    db_url = os.getenv("DATABASE_URL", "postgresql://gpe:gpe@localhost:5432/gpe")

    engine = create_engine(db_url)

    # Vérifier connexion
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✓ Connexion PostgreSQL OK")
    except Exception as e:
        logger.error(f"✗ Erreur connexion PostgreSQL : {e}")
        raise

    # Charger en base
    load_to_postgres(gdf, engine, "raw.gpe_gares_shapefile")

    logger.info("=== Ingestion GPE Shapefile terminée ===")


if __name__ == "__main__":
    main()
