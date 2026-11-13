"""
Tests d'intégration : chargement atomique des tables raw (#19).

Pour chaque script d'ingestion : une « ancienne » ligne est en base, on
provoque une vraie erreur PostgreSQL pendant le chargement, puis on
vérifie que l'ancienne ligne est toujours là (la table n'a pas été vidée).

Base temporaire uniquement (fixture test_engine, voir conftest.py).
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import psycopg2
import pytest
from shapely.geometry import LineString, Point
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from ingestion import fetch_gpe, fetch_gtfs, fetch_insee


def valeurs_en_base(engine: Engine, table: str, colonne: str) -> list[str]:
    """Retourne les valeurs d'une colonne de raw.<table>, triées."""
    with engine.connect() as conn:
        requete = text(f"SELECT {colonne} FROM raw.{table} ORDER BY 1")
        return list(conn.execute(requete).scalars())


def test_gtfs_echec_garde_les_anciennes_donnees(
    test_engine: Engine, tmp_path: Path
) -> None:
    """Doublon de stop_id : la clé primaire refuse, rien n'est perdu."""
    with test_engine.begin() as conn:
        conn.execute(text("INSERT INTO raw.gtfs_stops (stop_id) VALUES ('ANCIEN')"))
    (tmp_path / "stops.txt").write_text("stop_id\nA\nA\n")

    with pytest.raises(DBAPIError):
        fetch_gtfs.load_to_postgres(tmp_path, test_engine)

    assert valeurs_en_base(test_engine, "gtfs_stops", "stop_id") == ["ANCIEN"]


def test_insee_echec_garde_les_anciennes_donnees(
    test_engine: Engine,
) -> None:
    """Doublon de code_commune : la clé primaire refuse, rien n'est perdu."""
    with test_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO raw.insee_communes (code_commune) VALUES ('ANCIEN')")
        )
    df = pd.DataFrame({"code_commune": ["75101", "75101"]})

    with pytest.raises(DBAPIError):
        fetch_insee.load_to_postgres(df, "insee_communes", test_engine)

    assert valeurs_en_base(test_engine, "insee_communes", "code_commune") == ["ANCIEN"]


def test_gpe_echec_garde_les_anciennes_donnees(test_engine: Engine) -> None:
    """Une ligne au lieu d'un point : GEOMETRY(Point) refuse."""
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO raw.gpe_gares (nom_gare, geometry) VALUES "
                "('ANCIENNE', ST_SetSRID(ST_MakePoint(2.35, 48.85), 4326))"
            )
        )
    gdf = gpd.GeoDataFrame(
        {"nom_gare": ["Gare A", "Gare B"]},
        geometry=[Point(2.3, 48.8), LineString([(2.3, 48.8), (2.4, 48.9)])],
        crs="EPSG:4326",
    )

    # COPY passe par le curseur psycopg2 brut : l'erreur peut ne pas être
    # enveloppée par SQLAlchemy.
    with pytest.raises((DBAPIError, psycopg2.Error)):
        fetch_gpe.load_to_postgres(gdf, test_engine)

    assert valeurs_en_base(test_engine, "gpe_gares", "nom_gare") == ["ANCIENNE"]
