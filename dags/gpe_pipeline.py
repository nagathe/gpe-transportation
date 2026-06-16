"""
DAG : data_ingestion_pipeline
=============================
Pipeline principal pour l'ingestion des données du projet Grand Paris Express (GPE).

Architecture :
    ┌─ fetch_gpe ──────────────────────────┬─ quality_check_gpe ──────┐
    │                                      │                          │
    ├─ fetch_insee ────────────────────────┼─ quality_check_insee ────┼─ Succès
    │                                      │                          │
    └─ fetch_gtfs ─────────────────────────┼─ quality_check_gtfs ─────┘

Étapes :
    1. Les 3 ingestions (fetch_gpe, fetch_insee, fetch_gtfs) s'exécutent EN PARALLÈLE
       - Chaque ingestion télécharge, extrait et charge les données brutes en PostgreSQL
       - Les données existantes sont remplacées (TRUNCATE + INSERT)

    2. Les quality checks s'exécutent EN PARALLÈLE (après leurs ingestions respectives)
       - Vérifient que les données ont bien été chargées
       - Lèvent une exception en cas de problème

    3. Si tous les checks passent, le DAG réussit

Schedule : @hourly (toutes les heures) - TEST UNIQUEMENT
    À changer plus tard en @daily ou en event-driven si les données changent réellement

Auteur : Agathe
Créé : 2024
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import create_engine, text

from ingestion.fetch_gpe import main as fetch_gpe_main
from ingestion.fetch_gtfs import main as fetch_gtfs_main
from ingestion.fetch_insee import main as fetch_insee_main

# ============================================================================
# Fonctions de quality check
# ============================================================================


def quality_check_gpe() -> None:
    """
    Vérifie que les données GPE ont bien été ingérées.

    Contrôles :
        - La table raw.gpe_gares doit contenir au moins 1 ligne

    Lève :
        AssertionError si aucune données GPE n'a été trouvée
    """
    engine = create_engine("postgresql://...")  # TODO: utiliser config depuis env vars
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.gpe_gares"))
        count = result.scalar()
        assert count is not None and count > 0, "Aucune données GPE ingérées"
        print(f"✅ GPE : {count} gares ingérées")


def quality_check_insee() -> None:
    """
    Vérifie que les données INSEE ont bien été ingérées.

    Contrôles :
        - La table raw.insee doit contenir au moins 1 ligne

    Lève :
        AssertionError si aucune données INSEE n'a été trouvée
    """
    engine = create_engine("postgresql://...")  # TODO: utiliser config depuis env vars
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.insee"))
        count = result.scalar()
        assert count is not None and count > 0, "Aucune données INSEE ingérées"
        print(f"✅ INSEE : {count} communes ingérées")


def quality_check_gtfs() -> None:
    """
    Vérifie que les données GTFS ont bien été ingérées.

    Contrôles :
        - La table raw.gtfs_stops doit contenir au moins 1 ligne

    Lève :
        AssertionError si aucune données GTFS n'a été trouvée
    """
    engine = create_engine("postgresql://...")  # TODO: utiliser config depuis env vars
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw.gtfs_stops"))
        count = result.scalar()
        assert count is not None and count > 0, "Aucune données GTFS ingérées"
        print(f"✅ GTFS : {count} arrêts ingérés")


# ============================================================================
# Définition du DAG
# ============================================================================

with DAG(
    dag_id="data_ingestion_pipeline",
    description="Pipeline d'ingestion des données brutes (GPE, INSEE, GTFS)",
    start_date=datetime(2024, 1, 1),  # Date de départ historique
    schedule_interval="@hourly",  # Lancement toutes les heures (TEST)
    catchup=False,  # Ne pas rattraper les exécutions manquées du passé
    tags=["ingestion", "gpe"],  # Tags pour filtrer dans l'UI Airflow
    doc_md=__doc__,  # Documentation visible dans l'UI Airflow
) as dag:
    # ─────────────────────────────────────────────────────────────────────
    # Étape 1 : Ingestion des données brutes (exécution en parallèle)
    # ─────────────────────────────────────────────────────────────────────

    fetch_gpe = PythonOperator(
        task_id="fetch_gpe",
        python_callable=fetch_gpe_main,
        doc="Télécharge, extrait et charge les données des gares GPE",
    )

    fetch_insee = PythonOperator(
        task_id="fetch_insee",
        python_callable=fetch_insee_main,
        doc="Télécharge, extrait et charge les données INSEE (communes IDF)",
    )

    fetch_gtfs = PythonOperator(
        task_id="fetch_gtfs",
        python_callable=fetch_gtfs_main,
        doc="Télécharge, extrait et charge les données GTFS (transport)",
    )

    # ─────────────────────────────────────────────────────────────────────
    # Étape 2 : Quality checks des données ingérées (exécution en parallèle)
    # ─────────────────────────────────────────────────────────────────────

    check_gpe = PythonOperator(
        task_id="quality_check_gpe",
        python_callable=quality_check_gpe,
        doc="Vérifie que la table raw.gpe_gares contient des données",
    )

    check_insee = PythonOperator(
        task_id="quality_check_insee",
        python_callable=quality_check_insee,
        doc="Vérifie que la table raw.insee contient des données",
    )

    check_gtfs = PythonOperator(
        task_id="quality_check_gtfs",
        python_callable=quality_check_gtfs,
        doc="Vérifie que la table raw.gtfs_stops contient des données",
    )

    # ─────────────────────────────────────────────────────────────────────
    # Définition des dépendances
    # ─────────────────────────────────────────────────────────────────────
    # Format : task1 >> task2 signifie "task1 puis task2"

    fetch_gpe >> check_gpe
    fetch_insee >> check_insee
    fetch_gtfs >> check_gtfs
