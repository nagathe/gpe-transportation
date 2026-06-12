SHELL := /bin/bash
PYTHON ?= python
DBT_DIR := dbt

.DEFAULT_GOAL := help

.PHONY: help \
	docker-up docker-down \
	check-db-url db-init \
	ingest ingest-gtfs ingest-insee ingest-gpe \
	dbt-run dbt-test dbt-build \
	test test-unit test-integration \
	lint format typecheck all

help:
	@printf "Commandes disponibles:\n"
	@printf "  make docker-up         Demarre Postgres, Airflow et Grafana\n"
	@printf "  make docker-down       Arrete les services Docker\n"
	@printf "  make db-init           Initialise schemas/extensions/tables via init.sql\n"
	@printf "  make ingest            Lance les 3 ingestions: GTFS, INSEE, GPE\n"
	@printf "  make ingest-gtfs       Lance uniquement l'ingestion GTFS\n"
	@printf "  make ingest-insee      Lance uniquement l'ingestion INSEE\n"
	@printf "  make ingest-gpe        Lance uniquement l'ingestion GPE\n"
	@printf "  make dbt-run           Execute les modeles dbt\n"
	@printf "  make dbt-test          Execute les tests dbt\n"
	@printf "  make test-unit         Execute les tests unitaires\n"
	@printf "  make test-integration  Execute les tests d'integration\n"
	@printf "  make test              Execute toute la suite pytest\n"
	@printf "  make lint              Verifie black, isort et flake8\n"
	@printf "  make format            Formate le code Python\n"
	@printf "  make typecheck         Execute mypy\n"
	@printf "  make all               db-init, ingest, dbt-run, dbt-test\n"

docker-up:
	docker compose up -d

docker-down:
	docker compose down

check-db-url:
	@test -n "$$DATABASE_URL" || (echo "DATABASE_URL doit etre defini, ex: postgresql://gpe:gpe@localhost:5432/gpe" && exit 1)

db-init: check-db-url
	psql "$$DATABASE_URL" -f init.sql

ingest: ingest-gtfs ingest-insee ingest-gpe

ingest-gtfs: check-db-url
	$(PYTHON) ingestion/fetch_gtfs.py

ingest-insee: check-db-url
	$(PYTHON) ingestion/fetch_insee.py

ingest-gpe: check-db-url
	$(PYTHON) ingestion/fetch_gpe.py

dbt-run:
	cd $(DBT_DIR) && dbt run

dbt-test:
	cd $(DBT_DIR) && dbt test

dbt-build:
	cd $(DBT_DIR) && dbt build

test:
	pytest tests/

test-unit:
	pytest tests/unit/

test-integration:
	pytest tests/integration/

lint:
	black --check .
	isort --check-only .
	flake8 .

format:
	black .
	isort .

typecheck:
	mypy ingestion tests

all: db-init ingest dbt-run dbt-test
