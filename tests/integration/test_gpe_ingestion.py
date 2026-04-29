import pytest
import sqlalchemy
from sqlalchemy import text

ENGINE = sqlalchemy.create_engine("postgresql://gpe:gpe@localhost:5432/gpe")

EXPECTED_COLUMNS = {
    "nom_gare",
    "ligne",
    "longitude",
    "latitude",
    "mise_en_service",
    "statut",
}
CRITICAL_COLUMNS = ["nom_gare", "ligne", "longitude", "latitude"]


def test_table_exists() -> None:
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
    with ENGINE.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.gpe_gares"))
        assert result.scalar() > 0


def test_expected_columns_present() -> None:
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
        assert EXPECTED_COLUMNS.issubset(columns)


@pytest.mark.parametrize("column", CRITICAL_COLUMNS)
def test_no_nulls_on_critical_columns(column: str) -> None:
    with ENGINE.connect() as conn:
        result = conn.execute(
            text(
                f"""
            SELECT COUNT(*) FROM raw.gpe_gares WHERE {column} IS NULL
        """
            )
        )
        assert result.scalar() == 0
