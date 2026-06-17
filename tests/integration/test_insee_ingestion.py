# tests/integration/test_insee_ingestion.py
"""
Tests d'intégration pour l'ingestion INSEE.
Vérifie que les données INSEE sont correctement chargées en base.
Les colonnes sont en minuscules (renommage appliqué dans fetch_insee.py).
"""

import os

import pytest
from sqlalchemy import create_engine, text

ENGINE = create_engine(os.environ["DATABASE_URL"])


class TestINSEEIngestion:
    """Tests d'intégration pour raw.insee_communes."""

    def test_table_exists(self):
        """Vérifie que la table raw.insee_communes existe."""
        with ENGINE.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'raw' AND table_name = 'insee_communes'
                """
                )
            ).scalar()
            assert count == 1, "Table raw.insee_communes n'existe pas"

    def test_columns_exist(self):
        """Vérifie que les colonnes attendues existent (en minuscules)."""
        with ENGINE.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'raw' AND table_name = 'insee_communes'
                """
                )
            ).fetchall()
            columns = {row[0] for row in result}

            # Les colonnes sont renommées en minuscules par fetch_insee.py
            expected = {
                "code_commune",
                "population",
                "revenu_median",
                "nb_chomeurs",
                "nb_actifs",
                "nb_menages",
                "taux_chomage",
                "latitude",
                "longitude",
            }
            missing = expected - columns
            assert (
                missing == set()
            ), f"Colonnes manquantes dans raw.insee_communes : {missing}"

    def test_data_types(self):
        """Vérifie que les types de données sont corrects."""
        with ENGINE.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'raw' AND table_name = 'insee_communes'
                    ORDER BY ordinal_position
                """
                )
            ).fetchall()
            columns = {row[0]: row[1] for row in result}

            assert (
                columns["code_commune"] == "text"
            ), f"code_commune doit être text, trouvé {columns['code_commune']}"
            cols = [
                "population",
                "revenu_median",
                "nb_chomeurs",
                "nb_actifs",
            ]
            for col in cols:
                expected_type = "double precision"
                actual_type = columns[col]
                msg = f"{col} doit être {expected_type}, trouvé {actual_type}"
                assert actual_type == expected_type, msg

    def test_code_commune_not_null(self):
        """Vérifie que code_commune (clé primaire) n'a pas de NULLs."""
        with ENGINE.connect() as conn:
            query = (
                "SELECT COUNT(*) FROM raw.insee_communes " "WHERE code_commune IS NULL"
            )
            null_count = conn.execute(text(query)).scalar()
            msg = f"NULLs trouvés dans code_commune : {null_count}"
            assert null_count == 0, msg

    def test_data_not_empty(self):
        """Vérifie que la table n'est pas vide."""
        with ENGINE.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM raw.insee_communes")
            ).scalar()
            assert count > 0, "Table raw.insee_communes est vide"

    def test_code_commune_unique(self):
        """Vérifie que les codes communes sont uniques."""
        with ENGINE.connect() as conn:
            total, unique = conn.execute(
                text(
                    """
                    SELECT COUNT(*), COUNT(DISTINCT code_commune)
                    FROM raw.insee_communes
                """
                )
            ).fetchone()
            msg = (
                f"Doublons détectés : {total} rows mais "
                f"{unique} code_commune uniques"
            )
            assert total == unique, msg

    def test_revenu_median_coverage(self):
        """Vérifie que revenu_median a au moins 80% de couverture."""
        with ENGINE.connect() as conn:
            total, with_val, coverage_pct = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) as total,
                        COUNT(revenu_median) as with_val,
                        ROUND(
                            100.0 * COUNT(revenu_median) / COUNT(*),
                            2
                        ) as pct
                    FROM raw.insee_communes
                """
                )
            ).fetchone()
            msg = (
                f"revenu_median couverture insuffisante : "
                f"{coverage_pct}% ({with_val}/{total})"
            )
            assert coverage_pct >= 80, msg

    def test_taux_chomage_coverage(self):
        """Vérifie que taux_chomage a au moins 35% de couverture."""
        with ENGINE.connect() as conn:
            total, with_val, coverage_pct = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) as total,
                        COUNT(taux_chomage) as with_val,
                        ROUND(
                            100.0 * COUNT(taux_chomage) / COUNT(*),
                            2
                        ) as pct
                    FROM raw.insee_communes
                """
                )
            ).fetchone()
            msg = (
                f"taux_chomage couverture insuffisante : "
                f"{coverage_pct}% ({with_val}/{total})"
            )
            assert coverage_pct >= 35, msg

    def test_revenu_median_reasonable_values(self):
        """Vérifie que les revenus médians sont dans une plage raisonnable."""
        with ENGINE.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT MIN(revenu_median), MAX(revenu_median)
                    FROM raw.insee_communes
                    WHERE revenu_median IS NOT NULL
                """
                )
            ).fetchone()

            if result[0] is None:
                pytest.skip("revenu_median : aucune donnée non-NULL")

            min_val, max_val = result
            msg_min = f"Revenu médian anormalement bas : {min_val}€"
            assert min_val >= 10000, msg_min
            msg_max = f"Revenu médian anormalement haut : {max_val}€"
            assert max_val <= 100000, msg_max

    def test_taux_chomage_reasonable_values(self):
        """Vérifie que les taux de chômage sont entre 0 et 1 (ratio, pas %)."""
        with ENGINE.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT MIN(taux_chomage), MAX(taux_chomage)
                    FROM raw.insee_communes
                    WHERE taux_chomage IS NOT NULL
                """
                )
            ).fetchone()

            if result[0] is None:
                pytest.skip("taux_chomage : aucune donnée non-NULL")

            min_val, max_val = result
            msg_min = f"Taux de chômage négatif : {min_val}"
            assert min_val >= 0, msg_min
            msg_max = f"Taux de chômage > 1 (ratio attendu) : {max_val}"
            assert max_val <= 1, msg_max

    def test_coordonnees_idf_plausibles(self):
        """Vérifie que les coordonnées sont bien en Île-de-France."""
        with ENGINE.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM raw.insee_communes
                    WHERE latitude NOT BETWEEN 48.0 AND 49.5
                       OR longitude NOT BETWEEN 1.4 AND 3.6
                """
                )
            ).scalar()
            assert result == 0, f"{result} communes avec coordonnées hors IDF"
