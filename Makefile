# =============================================================================
# Makefile — Projet Grand Paris Express
#
# Usage :
#   make db-init        Crée les schemas et tables raw
#   make ingest         Lance tous les scripts d'ingestion
#   make dbt-run        Transformations dbt
#   make test           Lance les tests pytest
#   make lint           Vérifie le style (black, flake8, isort)
#   make all            Pipeline complet
# =============================================================================

.PHONY: db-init ingest dbt-run test lint all

# -----------------------------------------------------------------------------
# Base de données
# -----------------------------------------------------------------------------

db-init:
    psql $(DATABASE_URL) -f db/init_schemas.sql
    psql $(DATABASE_URL) -f db/create_tables.sql

# -----------------------------------------------------------------------------
# Ingestion
# -----------------------------------------------------------------------------

ingest:
    python ingestion/fetch_gtfs.py
    python ingestion/fetch_insee.py
    python ingestion/fetch_gpe.py

# -----------------------------------------------------------------------------
# Transformations dbt
# -----------------------------------------------------------------------------

dbt-run:
    cd dbt && dbt run

dbt-test:
    cd dbt && dbt test

# -----------------------------------------------------------------------------
# Qualité
# -----------------------------------------------------------------------------

lint:
    black --check .
    isort --check .
    flake8 .

format:
    black .
    isort .

test:
    pytest tests/

# -----------------------------------------------------------------------------
# Pipeline complet
# -----------------------------------------------------------------------------

all: db-init ingest dbt-run

