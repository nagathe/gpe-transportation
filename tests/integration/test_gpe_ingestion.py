# tests/integration/test_gpe_ingestion.py
"""
Tests d'intégration pour l'ingestion GPE (shapefile → raw.gpe_gares).
Vérifie que la table est bien chargée avec les bonnes colonnes et données.
"""

import os

import pytest
import sqlalchemy
from sqlalchemy import text

ENGINE = sqlalchemy.create_engine(os.environ["DATABASE_URL"])

# Colonnes produites par fetch_gpe.py (version shapefile)
EXPECTED_COLUMNS = {"nom_gare", "ligne_gpe", "interconnexion", "source", "geometry"}
CRITICAL_COLUMNS = ["nom_gare", "ligne_gpe"]


def test_table_exists() -> None:
    """Vérifie que la table raw.gpe_gares existe."""
    with ENGINE.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'raw' AND table_name = 'gpe_gares'
                )
            """
            )
        )
        assert result.scalar() is True


def test_table_has_rows() -> None:
    """Vérifie que la table contient des données."""
    with ENGINE.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.gpe_gares"))
        assert result.scalar() > 0


def test_expected_columns_present() -> None:
    """Vérifie que toutes les colonnes attendues sont présentes."""
    with ENGINE.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'raw' AND table_name = 'gpe_gares'
            """
            )
        )
        columns = {row[0] for row in result}
        assert EXPECTED_COLUMNS.issubset(
            columns
        ), f"Colonnes manquantes : {EXPECTED_COLUMNS - columns}"


@pytest.mark.parametrize("column", CRITICAL_COLUMNS)
def test_no_nulls_on_critical_columns(column: str) -> None:
    """Vérifie qu'il n'y a pas de NULLs dans les colonnes critiques."""
    with ENGINE.connect() as conn:
        result = conn.execute(
            text(f"SELECT COUNT(*) FROM raw.gpe_gares WHERE {column} IS NULL")
        )
        assert result.scalar() == 0, f"NULLs trouvés dans la colonne {column}"


def test_lignes_gpe_uniquement() -> None:
    """Vérifie que seules les lignes GPE (L15-L18) sont présentes."""
    with ENGINE.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT DISTINCT ligne_gpe FROM raw.gpe_gares
                WHERE ligne_gpe NOT IN ('L15', 'L16', 'L17', 'L18')
            """
            )
        )
        lignes_hors_gpe = [row[0] for row in result]
        assert lignes_hors_gpe == [], f"Lignes hors GPE trouvées : {lignes_hors_gpe}"
