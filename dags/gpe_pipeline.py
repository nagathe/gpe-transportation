"""
DAG : gpe_pipeline
==================
Pipeline principal pour l'ingestion des données GPE (Grand Paris Express).

Étapes :
    1. fetch_gpe : récupère les données des gares GPE depuis l'API data.gouv.fr

Schedule : quotidien (@daily)
Auteur : grand-paris-pipeline
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def fetch_gpe():
    """
    Récupère les données brutes des gares GPE.

    Source : API data.gouv.fr
    Output : données brutes en mémoire (TODO : stocker dans Postgres)
    """
    print("Fetching GPE data...")
    # TODO : appel API réel vers data.gouv.fr


# ---------------------------------------------------------------------------
# Définition du DAG
# ---------------------------------------------------------------------------

with DAG(
    dag_id="gpe_pipeline",
    start_date=datetime(2024, 1, 1),  # date de départ du pipeline
    schedule_interval="@daily",  # exécution quotidienne
    catchup=False,  # pas de rattrapage des runs passés
    tags=["gpe"],  # tag pour filtrer dans l'UI Airflow
    doc_md=__doc__,  # documentation visible dans l'UI Airflow
) as dag:
    # ------------------------------------------------------------------
    # Tâche 1 : ingestion des données brutes GPE
    # ------------------------------------------------------------------
    fetch = PythonOperator(
        task_id="fetch_gpe",  # nom affiché dans l'UI Airflow
        python_callable=fetch_gpe,  # fonction Python à exécuter
    )
