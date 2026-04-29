"""
Module d'ingestion des données INSEE communes Île-de-France.
Télécharge et charge les indicateurs socio-économiques en base PostgreSQL.
"""

import logging

import pandas as pd
import requests
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

INSEE_URL = (
    "https://www.insee.fr/fr/statistiques/fichier/2028307/"
    "base-cc-evol-struct-pop-2021.csv"
)

# Départements Île-de-France
DEPTS_IDF = {"75", "77", "78", "91", "92", "93", "94", "95"}

# COLONNES_UTILES = [
#     "CODGEO",
#     "LIBGEO",
#     "P21_POP",
#     "P21_POP1564",
#     "P21_CHOM1564",
# ]

# COLONNES_UTILES = [
#     "CODGEO",
#     "LIBGEO",
#     "P21_POP",
#     "MED20",
#     "TP6021"
# ]

COLONNES_UTILES = ["CODGEO", "LIBGEO", "MED20", "TP6020", "NBPERSMENFISC20"]


def download_insee(url: str = INSEE_URL, timeout: int = 30) -> bytes:
    """
    Télécharge le fichier INSEE depuis l'URL donnée.

    Args:
        url: URL du fichier CSV INSEE.
        timeout: Timeout HTTP en secondes.

    Returns:
        Contenu binaire du fichier CSV.

    Raises:
        requests.HTTPError: Si la réponse HTTP est une erreur.
    """
    logger.info("Téléchargement INSEE depuis %s", url)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    logger.info("Téléchargement terminé (%d bytes)", len(response.content))
    return response.content


def parse_insee(raw_bytes: bytes) -> pd.DataFrame:
    """Parse et nettoie les données INSEE communes.

    Args:
        raw_bytes: Contenu brut du fichier CSV INSEE (encodage latin-1, séparateur ;).

    Returns:
        DataFrame nettoyé filtré sur l'Île-de-France.

    Raises:
        KeyError: Si une colonne attendue est absente du fichier source.
    """
    from io import BytesIO

    df = pd.read_csv(BytesIO(raw_bytes), sep=";", encoding="latin-1", dtype=str)
    logger.info("Colonnes disponibles : %s", df.columns.tolist())

    # Vérifier que toutes les colonnes attendues sont présentes
    manquantes = [c for c in COLONNES_UTILES if c not in df.columns]
    if manquantes:
        raise KeyError(f"Colonnes manquantes : {manquantes}")

    df = df[COLONNES_UTILES].dropna(subset=["CODGEO"])

    # Filtrer sur l'Île-de-France (2 premiers caractères du code commune)
    df = df[df["CODGEO"].str[:2].isin(DEPTS_IDF)]

    # Convertir les colonnes numériques
    for col in COLONNES_UTILES:
        if col not in ("CODGEO", "LIBGEO"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    logger.info("%d communes IDF valides après nettoyage", len(df))
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
    """Point d'entrée principal du script d'ingestion INSEE.

    Args:
        database_url: URL de connexion Postgres (format SQLAlchemy).
    """
    logger.info("=== Début ingestion INSEE ===")

    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)

    # Créer le schéma raw s'il n'existe pas
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.commit()

    raw_bytes = download_insee()
    df = parse_insee(raw_bytes)
    load_to_postgres(df, "insee_communes", engine)

    logger.info("=== Ingestion INSEE terminée ===")


if __name__ == "__main__":
    import os

    db_url = os.environ["DATABASE_URL"]
    main(db_url)
