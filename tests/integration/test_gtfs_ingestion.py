"""
Tests d'intégration pour l'ingestion GTFS.

Vérifie que les données GTFS sont correctement chargées
en base PostgreSQL (schéma raw).
"""

import pandas as pd
import pytest
from pytest_postgresql import factories
from sqlalchemy import create_engine, text

# --- Fixtures PostgreSQL temporaire ---

postgresql_proc = factories.postgresql_proc(
    host="localhost",
    user="gpe",
)
postgresql = factories.postgresql("postgresql_proc")


# --- Helpers ---


def get_engine(postgresql) -> object:
    """Crée un engine SQLAlchemy connecté à la base de test temporaire.

    Args:
        postgresql: fixture pytest-postgresql avec les infos de connexion.

    Returns:
        Engine SQLAlchemy prêt à l'emploi.
    """
    return create_engine(
        f"postgresql+psycopg2://gpe:gpe@localhost/{postgresql.info.dbname}"
    )


def create_raw_schema(engine) -> None:
    """Crée le schéma raw s'il n'existe pas.

    Args:
        engine: Engine SQLAlchemy connecté à la base cible.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))


def load_stops(engine, df: pd.DataFrame) -> None:
    """Charge un DataFrame de stops dans raw.stops.

    Args:
        engine: Engine SQLAlchemy connecté à la base cible.
        df: DataFrame contenant les colonnes stop_id, stop_name, stop_lat, stop_lon.
    """
    df.to_sql("stops", engine, schema="raw", if_exists="replace", index=False)


# --- Fixtures de données ---


@pytest.fixture
def sample_stops() -> pd.DataFrame:
    """Retourne un DataFrame minimal de stops GTFS pour les tests.

    Returns:
        DataFrame avec 2 arrêts valides.
    """
    return pd.DataFrame(
        {
            "stop_id": ["STOP_001", "STOP_002"],
            "stop_name": ["Gare A", "Gare B"],
            "stop_lat": [48.8566, 48.9000],
            "stop_lon": [2.3522, 2.4000],
        }
    )


@pytest.fixture
def stops_in_db(postgresql, sample_stops):
    """Charge les stops de test en base et retourne l'engine.

    Fixture réutilisable par plusieurs tests qui ont besoin
    de données déjà présentes en base.

    Args:
        postgresql: fixture pytest-postgresql.
        sample_stops: fixture DataFrame de stops.

    Returns:
        Engine SQLAlchemy connecté à la base de test.
    """
    engine = get_engine(postgresql)
    create_raw_schema(engine)
    load_stops(engine, sample_stops)
    return engine


# --- Tests ---


def test_stops_count(stops_in_db):
    """Vérifie que le bon nombre de stops est chargé en base."""
    with stops_in_db.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.stops")).scalar()
    assert result == 2


def test_stops_columns_present(stops_in_db):
    """Vérifie que toutes les colonnes attendues sont présentes."""
    with stops_in_db.connect() as conn:
        result = (
            conn.execute(text("SELECT * FROM raw.stops LIMIT 1")).mappings().first()
        )

    expected_columns = {"stop_id", "stop_name", "stop_lat", "stop_lon"}
    assert expected_columns.issubset(set(result.keys()))


def test_stops_ids_correct(stops_in_db):
    """Vérifie que les stop_id chargés correspondent aux données source."""
    with stops_in_db.connect() as conn:
        rows = conn.execute(
            text("SELECT stop_id FROM raw.stops ORDER BY stop_id")
        ).fetchall()

    loaded_ids = {row[0] for row in rows}
    assert loaded_ids == {"STOP_001", "STOP_002"}


def test_stops_coordinates_are_floats(stops_in_db):
    """Vérifie que les coordonnées sont bien stockées comme des numériques."""
    with stops_in_db.connect() as conn:
        row = conn.execute(
            text("SELECT stop_lat, stop_lon FROM raw.stops WHERE stop_id = 'STOP_001'")
        ).fetchone()

    # On vérifie que ce sont bien des valeurs numériques exploitables
    assert isinstance(float(row[0]), float)
    assert isinstance(float(row[1]), float)


def test_empty_dataframe_loads_without_error(postgresql):
    """Vérifie qu'un DataFrame vide ne plante pas le chargement.

    Cas limite : si la source GTFS est vide (fichier corrompu ou absent),
    on ne doit pas avoir d'exception non gérée.
    """
    engine = get_engine(postgresql)
    create_raw_schema(engine)

    empty_df = pd.DataFrame(columns=["stop_id", "stop_name", "stop_lat", "stop_lon"])

    # Ne doit pas lever d'exception
    load_stops(engine, empty_df)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.stops")).scalar()

    assert result == 0


def test_replace_existing_data(postgresql, sample_stops):
    """Vérifie que if_exists='replace' écrase bien les données précédentes.

    Important : on ne veut pas d'accumulation de données entre deux runs.
    """
    engine = get_engine(postgresql)
    create_raw_schema(engine)

    # Premier chargement
    load_stops(engine, sample_stops)

    # Deuxième chargement avec données différentes
    new_stops = pd.DataFrame(
        {
            "stop_id": ["STOP_999"],
            "stop_name": ["Nouvelle Gare"],
            "stop_lat": [48.7000],
            "stop_lon": [2.1000],
        }
    )
    load_stops(engine, new_stops)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.stops")).scalar()

    # Doit contenir 1 seul stop, pas 3
    assert result == 1
