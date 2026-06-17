"""
Téléchargement et chargement des gares du Grand Paris Express en base raw.

Source  : Société du Grand Paris via data.gouv.fr — Shapefile EPSG:3949
Contenu : gares des lignes 15, 16, 17, 18 avec coordonnées GPS et métadonnées
"""

import logging
import os
import zipfile
from pathlib import Path

import geopandas as gpd
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

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

GPE_GARES_URL = (
    "https://static.data.gouv.fr/resources/"
    "point-de-localisation-des-gares-de-la-ligne-15-sud-et-ligne-16/"
    "20161219-110430/GPE_GARE_LOCALISATION.zip"
)

GPE_DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "gpe"

# Lignes du Grand Paris Express (hors prolongements RER existants)
LIGNES_GPE = {"L15", "L16", "L17", "L18"}


# ---------------------------------------------------------------------------
# Fonctions
# ---------------------------------------------------------------------------


def download_gpe(url: str, dest_dir: Path) -> Path:
    """Télécharge le ZIP des gares GPE et le sauvegarde sur disque.

    Args:
        url: URL du fichier ZIP sur data.gouv.fr.
        dest_dir: Dossier de destination.

    Returns:
        Chemin vers le ZIP téléchargé.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "gpe_gares.zip"

    if zip_path.exists():
        logger.info("ZIP déjà présent, téléchargement ignoré : %s", zip_path)
        return zip_path

    logger.info("Téléchargement GPE depuis %s", url)
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    zip_path.write_bytes(response.content)
    size_mb = zip_path.stat().st_size / 1e6
    logger.info("ZIP sauvegardé : %s (%.1f Mo)", zip_path, size_mb)
    return zip_path


def extract_gpe(zip_path: Path) -> Path:
    """Extrait le ZIP dans un sous-dossier et retourne son chemin.

    Args:
        zip_path: Chemin vers le ZIP téléchargé.

    Returns:
        Chemin vers le dossier d'extraction.
    """
    extract_dir = zip_path.parent / "extracted"
    extract_dir.mkdir(exist_ok=True)

    logger.info("Extraction du ZIP dans %s", extract_dir)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    return extract_dir


def parse_gpe(extract_dir: Path) -> gpd.GeoDataFrame:
    """Lit le shapefile GPE, reprojette en WGS84 et filtre sur les lignes GPE.

    Args:
        extract_dir: Dossier contenant le shapefile extrait.

    Returns:
        GeoDataFrame nettoyé avec colonnes normalisées.

    Raises:
        FileNotFoundError: Si aucun .shp n'est trouvé dans le dossier.
    """
    shp_files = list(extract_dir.glob("**/*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"Aucun shapefile trouvé dans {extract_dir}")

    shp_path = shp_files[0]
    logger.info("Lecture du shapefile : %s", shp_path)
    gdf = gpd.read_file(shp_path)
    logger.info("Colonnes shapefile : %s", gdf.columns.tolist())

    # Reprojection EPSG:3949 (Lambert-93 étendu) → EPSG:4326 (WGS84)
    if gdf.crs.to_epsg() != 4326:
        logger.info("Reprojection %s → EPSG:4326", gdf.crs.to_epsg())
        gdf = gdf.to_crs(epsg=4326)

    # Normalisation des colonnes
    gdf = gdf.rename(
        columns={
            "LIBELLE": "nom_gare",
            "LIGNE": "ligne_gpe",
            "CONNEX": "interconnexion",
            "producteur": "source",
        }
    )

    # Filtrage sur les lignes GPE uniquement
    avant = len(gdf)
    gdf = gdf[gdf["ligne_gpe"].isin(LIGNES_GPE)].copy()
    logger.info("Filtrage lignes GPE : %d → %d gares", avant, len(gdf))

    cols = ["nom_gare", "ligne_gpe", "interconnexion", "source", "geometry"]
    return gdf[cols]


def load_to_postgres(gdf: gpd.GeoDataFrame, engine: Engine) -> None:
    """Charge le GeoDataFrame en base dans raw.gpe_gares.
    Utilise TRUNCATE + INSERT pour préserver les vues dépendantes.

    Args:
        gdf: GeoDataFrame des gares GPE nettoyé.
        engine: Connexion SQLAlchemy vers PostgreSQL/PostGIS.
    """
    logger.info("Chargement de %d gares dans raw.gpe_gares", len(gdf))
    with engine.begin() as conn:
        exists = engine.dialect.has_table(conn, "gpe_gares", schema="raw")

    if exists:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE raw.gpe_gares"))
        gdf.to_postgis(
            name="gpe_gares",
            con=engine,
            schema="raw",
            if_exists="append",
            index=False,
        )
    else:
        gdf.to_postgis(
            name="gpe_gares",
            con=engine,
            schema="raw",
            if_exists="replace",
            index=False,
        )

    logger.info("Chargement terminé")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def main(database_url: str) -> None:
    """Enchaîne téléchargement → extraction → transformation → chargement.

    Args:
        database_url: URL de connexion PostgreSQL (format SQLAlchemy).
    """
    logger.info("=== Début ingestion GPE ===")
    engine = create_engine(database_url)

    zip_path = download_gpe(GPE_GARES_URL, GPE_DATA_DIR)
    extract_dir = extract_gpe(zip_path)
    gdf = parse_gpe(extract_dir)
    load_to_postgres(gdf, engine)

    logger.info("=== Ingestion GPE terminée ===")


if __name__ == "__main__":
    main(os.environ["DATABASE_URL"])
