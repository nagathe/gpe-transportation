"""
Module d'ingestion des données INSEE communes Île-de-France.
Télécharge et charge les indicateurs socio-économiques en base PostgreSQL.
"""

import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

logger = logging.getLogger(__name__)

# Depuis le 22/07/2026, l'INSEE publie le dossier complet en CSV (7 Go
# décompressé) et en Parquet, format recommandé : on ne lit que les colonnes utiles.
INSEE_URL = (
    "https://www.insee.fr/fr/statistiques/fichier/5359146/dossier_complet.parquet"
)
INSEE_PATH = Path("data/raw/insee/dossier_complet.parquet")
CHUNK_SIZE = 1024 * 1024  # 1 Mo

DEPTS_IDF = {"75", "77", "78", "91", "92", "93", "94", "95"}

# Niveaux géographiques retenus : communes (COM) et arrondissements (ARM)
GEO_OBJECTS = ["COM", "ARM"]

# Le fichier INSEE est en format long : une ligne = une mesure d'un territoire
# pour une année. On retient (table ID_TAB, mesure TAB_MEASURE) -> colonne cible.
MESURES_INSEE = {
    ("POP_T1", "POP"): "population",
    ("REV_T1", "MED_SL"): "revenu_median",  # niveau de vie médian (Filosofi)
    ("EMP_T1", "POP_EMPSTA_ENQ_2_AGE_Y15T64"): "nb_chomeurs",  # chômeurs 15-64 ans
    ("EMP_T1", "POP_EMPSTA_ENQ_1T2_AGE_Y15T64"): "nb_actifs",  # actifs 15-64 ans
    # Résidences principales = nombre de ménages
    ("FAM_T1", "DWELLINGS_OCS_DW_MAIN"): "nb_menages",
}
COLONNES_SORTIE = list(MESURES_INSEE.values())
COLONNES_LECTURE = [
    "GEO_REF",
    "GEO",
    "TIME_PERIOD",
    "ID_TAB",
    "TAB_MEASURE",
    "OBS_VALUE",
    "UNIT_MULT",
]
# Pas de taux de pauvreté dans ce fichier de données
# Calcul : taux_chomage = nb_chomeurs / nb_actifs (suffisant pour précarité)

# URLs GeoAPI par département pour éviter de télécharger toute la France
# Format : /departements/{code}/communes
GEO_API_DEPT_URL = (
    "https://geo.api.gouv.fr/departements/{dept}/communes"
    "?fields=code,{fields}&format=json"
)


def download_insee(
    url: str = INSEE_URL, dest: Path = INSEE_PATH, timeout: int = 120
) -> Path:
    """
    Télécharge le fichier INSEE (Parquet) sur disque, par morceaux.

    Si le fichier est déjà présent, il est réutilisé : une panne du site
    n'empêche pas de relancer le pipeline. Le téléchargement passe par un
    fichier temporaire pour ne jamais laisser un fichier incomplet.

    Args:
        url: URL du fichier Parquet INSEE.
        dest: Chemin de destination du fichier.
        timeout: Timeout HTTP en secondes.

    Returns:
        Path vers le fichier téléchargé.

    Raises:
        requests.HTTPError: Si la réponse HTTP est une erreur.
    """
    if dest.exists():
        logger.info("Fichier déjà présent, téléchargement ignoré : %s", dest)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".part")
    logger.info("Téléchargement INSEE depuis %s", url)
    try:
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with tmp_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
    except requests.HTTPError as e:
        logger.error("Échec du téléchargement INSEE : %s", e)
        tmp_path.unlink(missing_ok=True)
        raise
    except requests.ConnectionError as e:
        logger.error("Erreur réseau INSEE : %s", e)
        tmp_path.unlink(missing_ok=True)
        raise

    tmp_path.rename(dest)
    logger.info(
        "Téléchargement terminé : %s (%.1f Mo)", dest, dest.stat().st_size / 1e6
    )
    return dest


def parse_insee(parquet_path: Path) -> pd.DataFrame:
    """Lit le Parquet INSEE (format long) et retourne une ligne par commune.

    Ne lit que les lignes utiles (communes et arrondissements, tables et
    mesures de MESURES_INSEE), garde le dernier millésime disponible de chaque
    mesure, puis pivote pour obtenir une colonne par indicateur.

    Args:
        parquet_path: Chemin du fichier Parquet INSEE.

    Returns:
        DataFrame filtré sur l'Île-de-France avec les colonnes code_commune,
        population, revenu_median, nb_chomeurs, nb_actifs, nb_menages et
        taux_chomage (calculé).

    Raises:
        KeyError: Si une colonne ou une mesure attendue est absente du fichier.
    """
    # pyarrow n'est pas typé : appels ignorés ligne par ligne pour mypy strict
    colonnes_fichier = pq.read_schema(parquet_path).names  # type: ignore[no-untyped-call]
    logger.info("Colonnes du fichier : %s", colonnes_fichier)

    attendues = COLONNES_LECTURE + ["GEO_OBJECT"]
    manquantes = [c for c in attendues if c not in colonnes_fichier]
    if manquantes:
        raise KeyError(f"Colonnes manquantes : {manquantes}")

    tables = sorted({table for table, _ in MESURES_INSEE})
    mesures = sorted({mesure for _, mesure in MESURES_INSEE})
    filtres = [
        ("GEO_OBJECT", "in", GEO_OBJECTS),
        ("ID_TAB", "in", tables),
        ("TAB_MEASURE", "in", mesures),
    ]
    table = pq.read_table(  # type: ignore[no-untyped-call]
        parquet_path, columns=COLONNES_LECTURE, filters=filtres
    )
    df = table.to_pandas()

    # Île-de-France : 2 premiers caractères du code géographique
    df = df[df["GEO"].str[:2].isin(DEPTS_IDF)].copy()

    # Associe chaque (table, mesure) à sa colonne cible ; écarte les autres paires
    cles = list(zip(df["ID_TAB"], df["TAB_MEASURE"]))
    df["colonne"] = [MESURES_INSEE.get(cle) for cle in cles]
    df = df.dropna(subset=["colonne"])

    absentes = [c for c in COLONNES_SORTIE if c not in set(df["colonne"])]
    if absentes:
        raise KeyError(f"Mesures manquantes : {absentes}")

    # Valeur = OBS_VALUE x 10^UNIT_MULT (UNIT_MULT absent = 0)
    multiplicateur = 10 ** pd.to_numeric(df["UNIT_MULT"], errors="coerce").fillna(0)
    df["valeur"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce") * multiplicateur

    # Dernier millésime disponible, puis dernier millésime géographique
    df = df.sort_values(["TIME_PERIOD", "GEO_REF"])
    df = df.drop_duplicates(["GEO", "colonne"], keep="last")
    annees = df.groupby("colonne")["TIME_PERIOD"].agg(["min", "max"])
    logger.info("Millésimes utilisés par indicateur :\n%s", annees)

    df = df.pivot(index="GEO", columns="colonne", values="valeur")
    df.columns.name = None
    df.index.name = "code_commune"
    df = df.reindex(columns=COLONNES_SORTIE).reset_index()

    # Calcul du taux de chômage : nb_chomeurs / nb_actifs
    # Résultat entre 0 et 1, NaN si nb_actifs est nul ou manquant
    df["taux_chomage"] = df["nb_chomeurs"] / df["nb_actifs"].where(df["nb_actifs"] > 0)

    logger.info("%d communes IDF valides après nettoyage", len(df))
    return df.reset_index(drop=True)


def _fetch_geo_data(fields: str) -> list[dict[str, Any]]:
    """Télécharge données géographiques depuis GeoAPI pour départements IDF.

    Interroge l'API département par département pour éviter de télécharger
    l'ensemble des communes françaises.

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
        data = response.json()
        rows.extend(data)
        logger.info(
            "Département %s : %d communes récupérées",
            dept,
            len(data),
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
    logger.info("Téléchargement coordonnées depuis GeoAPI (par département)")

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
            df.to_sql(
                table,
                engine,
                schema="raw",
                if_exists="append",
                index=False,
            )
        else:
            df.to_sql(
                table,
                engine,
                schema="raw",
                if_exists="replace",
                index=False,
            )

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
    logger.info("Téléchargement noms communes depuis GeoAPI (par département)")

    raw = _fetch_geo_data(fields="nom")

    rows = [
        {"code_commune": c["code"], "nom_commune": c["nom"]} for c in raw if "nom" in c
    ]

    # Paris : GeoAPI retourne 75056 mais INSEE utilise arrondissements
    # 75101-75120
    paris_rows = [
        {
            "code_commune": f"751{i:02d}",
            "nom_commune": (f"Paris {i}{'er' if i == 1 else 'e'} Arrondissement"),
        }
        for i in range(1, 21)
    ]
    rows.extend(paris_rows)

    # Saint-Ouen : renommée Saint-Ouen-sur-Seine en 2019
    rows.append({"code_commune": "93059", "nom_commune": "Saint-Ouen-sur-Seine"})

    df = pd.DataFrame(rows)
    logger.info("%d noms de communes récupérés", len(df))

    load_to_postgres(df, "commune_names", engine)


def main(database_url: str) -> None:
    """Point d'entrée principal du script d'ingestion INSEE.

    Args:
        database_url: URL de connexion Postgres (format SQLAlchemy).
    """
    logger.info("=== Début ingestion INSEE ===")

    os.makedirs("data/raw/insee", exist_ok=True)
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
