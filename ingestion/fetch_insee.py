"""
Module d'ingestion des données INSEE communes Île-de-France.
Télécharge et charge les indicateurs socio-économiques en base PostgreSQL.
"""

import logging
import os
import zipfile

# from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

logger = logging.getLogger(__name__)

os.makedirs("data/raw/insee", exist_ok=True)

INSEE_URL = (
    "https://www.insee.fr/fr/statistiques/fichier/5359146/" "dossier_complet.zip"
)

DEPTS_IDF = {"75", "77", "78", "91", "92", "93", "94", "95"}

COLONNES_INSEE = {
    "CODGEO": "code_commune",
    "P22_POP": "population",
    "MED_SL23": "revenu_median",
    "P22_CHOM1564": "nb_chomeurs",
    "P22_ACT1564": "nb_actifs",
    "C22_PMEN": "nb_menages",
}
# Pas de taux de pauvreté dans ce fichier de données
# on calculera juste taux_chomage = nb_chomeurs / nb_actifs. C'est suffisant pour l'analyse précarité vs mobilité

# URLs GeoAPI par département pour éviter de télécharger toute la France
# Format : /departements/{code}/communes
GEO_API_DEPT_URL = "https://geo.api.gouv.fr/departements/{dept}/communes?fields=code,{fields}&format=json"


def download_insee(url: str = INSEE_URL, timeout: int = 120) -> Path:
    """
    Télécharge le fichier INSEE depuis l'URL donnée.

    Args:
        url: URL du fichier ZIP INSEE.
        timeout: Timeout HTTP en secondes.

    Returns:
        Contenu binaire du fichier ZIP.

    Raises:
        requests.HTTPError: Si la réponse HTTP est une erreur.
    """
    # Le site INSEE bloque les requêtes sans User-Agent navigateur
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    logger.info("Téléchargement INSEE depuis %s", url)
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.HTTPError as e:
        logger.error("Échec du téléchargement INSEE : %s", e)
        raise
    except requests.ConnectionError as e:
        logger.error("Erreur réseau INSEE : %s", e)
        raise

    logger.info("Téléchargement terminé (%d bytes)", len(response.content))
    # return response.content
    zip_path = Path("data/raw/insee/dossier_complet.zip")
    zip_path.write_bytes(response.content)
    return zip_path


def parse_insee(zip_path: Path) -> pd.DataFrame:
    """Parse et nettoie les données INSEE communes.

    Renomme les colonnes INSEE vers des noms lisibles (cf. COLONNES_INSEE),
    calcule le taux de chômage et filtre sur l'Île-de-France.

    Args:
        zip_files: Contenu brut du fichier ZIP INSEE.

    Returns:
        DataFrame nettoyé filtré sur l'Île-de-France, colonnes renommées,
        avec colonne taux_chomage calculée.

    Raises:
        KeyError: Si une colonne attendue est absente du fichier source.
    """
    # Le fichier téléchargé est un ZIP contenant dossier_complet.csv
    with zipfile.ZipFile(zip_path) as zf:
        logger.info("Fichiers dans le ZIP : %s", zf.namelist())
        with zf.open("dossier_complet.csv") as f:
            df = pd.read_csv(
                f, sep=";", encoding="latin-1", dtype=str, low_memory=False
            )

    logger.info("Colonnes disponibles : %s", df.columns.tolist())

    manquantes = [c for c in COLONNES_INSEE if c not in df.columns]
    if manquantes:
        raise KeyError(f"Colonnes manquantes : {manquantes}")

    df = df[list(COLONNES_INSEE.keys())].dropna(subset=["CODGEO"])

    # Filtrer sur l'Île-de-France (2 premiers caractères du code commune)
    df = df[df["CODGEO"].str[:2].isin(DEPTS_IDF)]

    for col in COLONNES_INSEE:
        if col != "CODGEO":
            df[col] = pd.to_numeric(
                df[col].str.replace(",", "."), errors="coerce"
            )  # pour les décimales

    # Appliquer le renommage vers des noms lisibles définis dans COLONNES_INSEE
    df = df.rename(columns=COLONNES_INSEE)

    # Calcul du taux de chômage : nb_chomeurs / nb_actifs
    # Résultat entre 0 et 1, NaN si nb_actifs est nul ou manquant
    df["taux_chomage"] = df["nb_chomeurs"] / df["nb_actifs"]

    logger.info("%d communes IDF valides après nettoyage", len(df))
    return df.reset_index(drop=True)


def _fetch_geo_data(fields: str) -> list[dict]:
    """Télécharge les données géographiques depuis GeoAPI pour les départements IDF.

    Interroge l'API département par département pour éviter de télécharger
    l'ensemble des ~35 000 communes françaises.

    Args:
        fields: Champs GeoAPI à récupérer (ex: "code,centre" ou "code,nom").

    Returns:
        Liste de dictionnaires bruts retournés par l'API.
    """
    rows = []
    for dept in DEPTS_IDF:
        url = GEO_API_DEPT_URL.format(dept=dept, fields=fields)
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        rows.extend(response.json())
        logger.info(
            "Département %s : %d communes récupérées", dept, len(response.json())
        )
    return rows


def enrich_with_geo(df: pd.DataFrame) -> pd.DataFrame:
    """Enrichit les communes avec leurs coordonnées géographiques via GeoAPI.

    Interroge l'API département par département (IDF uniquement) pour limiter
    le volume de données téléchargées.

    Args:
        df: DataFrame INSEE avec colonne code_commune (après renommage).

    Returns:
        DataFrame enrichi avec colonnes latitude et longitude.
    """
    logger.info("Téléchargement coordonnées communes depuis GeoAPI (par département)")

    raw = _fetch_geo_data(fields="centre")

    rows = [
        {
            "code_commune": c["code"],
            "longitude": c["centre"]["coordinates"][0],
            "latitude": c["centre"]["coordinates"][1],
        }
        for c in raw
        if "centre" in c
    ]

    df_geo = pd.DataFrame(rows)
    df_enriched = df.merge(df_geo, on="code_commune", how="left")

    manquantes = df_enriched["latitude"].isna().sum()
    logger.info("%d communes sans coordonnées après merge", manquantes)

    return df_enriched


def load_to_postgres(df: pd.DataFrame, table: str, engine: Engine) -> None:
    """
    Charge un DataFrame dans PostgreSQL (schéma raw).
    Utilise TRUNCATE + INSERT pour préserver les vues dépendantes.

    Args:
        df: DataFrame à charger.
        table: Nom de la table cible.
        engine: Connexion SQLAlchemy.
    """
    logger.info("Chargement de %d lignes dans raw.%s", len(df), table)
    try:
        # Vérifie si la table existe déjà
        with engine.begin() as conn:
            exists = engine.dialect.has_table(conn, table, schema="raw")

        if exists:
            # Vide la table sans la supprimer (les vues dbt restent valides)
            with engine.begin() as conn:
                conn.execute(text(f"TRUNCATE TABLE raw.{table}"))
            df.to_sql(table, engine, schema="raw", if_exists="append", index=False)
        else:
            df.to_sql(table, engine, schema="raw", if_exists="replace", index=False)

        logger.info("Chargement terminé pour raw.%s", table)
    except Exception as e:
        logger.error("Échec chargement raw.%s : %s", table, e)
        raise


def fetch_commune_names(engine: Engine) -> None:
    """Télécharge les noms de communes IDF depuis GeoAPI et charge en raw.

    Interroge l'API département par département (IDF uniquement) pour limiter
    le volume de données téléchargées.

    Args:
        engine: Connexion SQLAlchemy.

    Raises:
        requests.HTTPError: Si l'appel API échoue.
    """
    logger.info("Téléchargement noms de communes depuis GeoAPI (par département)")

    raw = _fetch_geo_data(fields="nom")

    rows = [
        {"code_commune": c["code"], "nom_commune": c["nom"]} for c in raw if "nom" in c
    ]

    df = pd.DataFrame(rows)
    logger.info("%d noms de communes récupérés", len(df))

    load_to_postgres(df, "commune_names", engine)


def main(database_url: str) -> None:
    """Point d'entrée principal du script d'ingestion INSEE.

    Args:
        database_url: URL de connexion Postgres (format SQLAlchemy).
    """
    logger.info("=== Début ingestion INSEE ===")

    engine = create_engine(database_url)

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))

    zip_path = download_insee()
    df = parse_insee(zip_path)
    df = enrich_with_geo(df)
    load_to_postgres(df, "insee_communes", engine)
    fetch_commune_names(engine)

    logger.info("=== Ingestion INSEE terminée ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db_url = os.environ["DATABASE_URL"]
    main(db_url)
