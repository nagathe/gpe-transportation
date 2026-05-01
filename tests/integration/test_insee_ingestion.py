"""
Tests d'intégration pour l'ingestion INSEE.

Vérifie que les données INSEE sont correctement chargées en base.
"""

import pytest
from sqlalchemy import create_engine, text

# Connexion au conteneur Postgres via Docker
ENGINE = create_engine("postgresql://gpe:gpe@localhost:5432/gpe")


class TestINSEEIngestion:
    """Tests d'intégration pour raw.insee_communes."""

    def test_table_exists(self):
        """Vérifie que la table raw.insee_communes existe."""
        with ENGINE.connect() as conn:
            query = text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'raw' AND table_name = 'insee_communes'
            """
            )
            count = conn.execute(query).scalar()
            assert count == 1, "Table raw.insee_communes n'existe pas"

    def test_columns_exist(self):
        """Vérifie que les colonnes attendues existent."""
        with ENGINE.connect() as conn:
            query = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'raw' AND table_name = 'insee_communes'
            """
            )
            result = conn.execute(query).fetchall()
            columns = {row[0] for row in result}

            # Les colonnes sont en MAJUSCULES dans ta base
            expected = {"CODGEO", "MED21", "TP6021", "NBPERSMENFISC21"}
            missing = expected - columns
            assert (
                missing == set()
            ), f"Colonnes manquantes dans raw.insee_communes : {missing}"

    def test_data_types(self):
        """Vérifie que les types de données sont corrects."""
        with ENGINE.connect() as conn:
            query = text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'raw' AND table_name = 'insee_communes'
                ORDER BY ordinal_position
            """
            )
            result = conn.execute(query).fetchall()
            columns = {row[0]: row[1] for row in result}

            # CODGEO doit être text
            assert (
                columns["CODGEO"] == "text"
            ), f"CODGEO doit être text, trouvé {columns['CODGEO']}"

            # Les indicateurs doivent être double precision
            for col in ["MED21", "TP6021", "NBPERSMENFISC21"]:
                assert (
                    columns[col] == "double precision"
                ), f"{col} doit être double precision, trouvé {columns[col]}"

    def test_codgeo_not_null(self):
        """Vérifie que CODGEO (clé primaire) n'a pas de NULLs."""
        with ENGINE.connect() as conn:
            query = text(
                'SELECT COUNT(*) FROM raw.insee_communes WHERE "CODGEO" IS NULL'
            )
            null_count = conn.execute(query).scalar()
            assert (
                null_count == 0
            ), f"NULLs trouvés dans CODGEO (clé primaire) : {null_count} rows"

    def test_data_not_empty(self):
        """Vérifie que la table n'est pas vide."""
        with ENGINE.connect() as conn:
            query = text("SELECT COUNT(*) FROM raw.insee_communes")
            count = conn.execute(query).scalar()
            assert count > 0, "Table raw.insee_communes est vide"

    def test_codgeo_unique(self):
        """Vérifie que les codes communes sont uniques."""
        with ENGINE.connect() as conn:
            query = text(
                """
                SELECT COUNT(*), COUNT(DISTINCT "CODGEO")
                FROM raw.insee_communes
            """
            )
            total, unique = conn.execute(query).fetchone()
            assert (
                total == unique
            ), f"Doublons détectés : {total} rows mais {unique} CODGEO uniques"

    def test_med21_has_sufficient_coverage(self):
        """Vérifie que MED21 a au moins 80% de couverture."""
        with ENGINE.connect() as conn:
            query = text(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT("MED21") as with_med21,
                    ROUND(100.0 * COUNT("MED21") / COUNT(*), 2) as coverage_pct
                FROM raw.insee_communes
            """
            )
            total, with_med21, coverage_pct = conn.execute(query).fetchone()

            assert coverage_pct >= 80, (
                f"MED21 couverture insuffisante : {coverage_pct}% "
                f"({with_med21}/{total} communes)"
            )

    def test_tp6021_has_sufficient_coverage(self):
        """Vérifie que TP6021 a au moins 35% de couverture."""
        with ENGINE.connect() as conn:
            query = text(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT("TP6021") as with_tp6021,
                    ROUND(100.0 * COUNT("TP6021") / COUNT(*), 2) as coverage_pct
                FROM raw.insee_communes
            """
            )
            total, with_tp6021, coverage_pct = conn.execute(query).fetchone()

            assert coverage_pct >= 35, (
                f"TP6021 couverture insuffisante : {coverage_pct}% "
                f"({with_tp6021}/{total} communes)"
            )

    def test_med21_reasonable_values(self):
        """Vérifie que les revenus médians sont dans une plage raisonnable."""
        with ENGINE.connect() as conn:
            query = text(
                """
                SELECT MIN("MED21"), MAX("MED21")
                FROM raw.insee_communes
                WHERE "MED21" IS NOT NULL
            """
            )
            result = conn.execute(query).fetchone()

            # Gérer le cas où tout est NULL (très peu probable)
            if result[0] is None or result[1] is None:
                pytest.skip("MED21 : aucune donnée non-NULL")

            min_val, max_val = result

            # Revenus médians en Île-de-France : entre 10k€ et 100k€
            assert min_val >= 10000, f"Revenu médian anormalement bas : {min_val}€"
            assert max_val <= 100000, f"Revenu médian anormalement haut : {max_val}€"

    def test_tp6021_reasonable_values(self):
        """Vérifie que les taux de pauvreté sont entre 0 et 100."""
        with ENGINE.connect() as conn:
            query = text(
                """
                SELECT MIN("TP6021"), MAX("TP6021")
                FROM raw.insee_communes
                WHERE "TP6021" IS NOT NULL
            """
            )
            result = conn.execute(query).fetchone()

            # Gérer le cas où tout est NULL
            if result[0] is None or result[1] is None:
                pytest.skip("TP6021 : aucune donnée non-NULL")

            min_val, max_val = result

            assert min_val >= 0, f"Taux de pauvreté négatif détecté : {min_val}%"
            assert max_val <= 100, f"Taux de pauvreté > 100 détecté : {max_val}%"


# TODO: À améliorer
# =============================================================================
# 1. **Enrichissement des données** :
#    - Ajouter `nom_commune` (jointure avec fichier COG INSEE)
#    - Ajouter `latitude`, `longitude` (géolocalisation des centroides)
#    - Ajouter `population_totale` (données socioéconomiques plus riches)
#    - Ajouter `taux_chomage` (indicateur de précarité)
#
# 2. **Qualité des données** :
#    - Valider les codes géographiques (format de CODGEO = 5 chiffres)
#    - Vérifier la couverture géographique (Île-de-France uniquement ?)
#    - Déterminer les valeurs manquantes acceptables par colonne ✅ (via tests coverage)
#
# 3. **Performance** :
#    - Ajouter un index sur CODGEO (clé de jointure)
#    - Créer des statistiques pour les requêtes complexes
#
# 4. **Testabilité** :
#    - Créer une fixture pytest pour les connexions DB (DRY)
#    - Paramétrer les seuils de couverture (pas hardcodés)
#    - Ajouter des tests de performance (ingestion < 5 sec)
#
# 5. **Standardisation** :
#    - Convertir les colonnes en minuscules en staging (convention dbt)
#    - Ajouter des préfixes intelligibles (ex: `insee_revenu_median`)
