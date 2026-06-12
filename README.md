# Grand Paris Express — Pipeline Data

**Question centrale :** Le Grand Paris Express va-t-il réduire les inégalités de mobilité en banlieue ?

Ce projet mesure, commune par commune en Île-de-France, qui gagne en accessibilité avec le GPE —
et si ce sont bien les zones les plus précaires qui en bénéficient le plus.

---

## Architecture

```
Ingestion (Python)        Staging (dbt views)           Marts (dbt tables)
─────────────────         ───────────────────           ──────────────────
fetch_gtfs.py      →  stg_gtfs_stops            →  accessibilite_par_commune
fetch_insee.py     →  stg_insee_communes         →  gain_mobilite
fetch_gpe.py       →  stg_gpe_gares              →  precarite_vs_mobilite
```

**Sources de données :**
- GTFS IDFM — réseau de transport actuel (arrêts, lignes)
- INSEE — revenus, chômage, population par commune IDF
- Shapefile SdGP — futures gares GPE (lignes 15/16/17/18)

---

## Installation

### Prérequis
- Docker Desktop
- Python 3.11+

### 1. Configurer l'environnement

```bash
cp .env.exemple .env
# Remplir les valeurs dans .env
```

### 2. Installer les dépendances Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pre-commit install
```

### 3. Démarrer les services

```bash
make docker-up
```

| Service    | URL                   |
|------------|-----------------------|
| Airflow    | http://localhost:8080 |
| Grafana    | http://localhost:3000 |
| PostgreSQL | localhost:5432        |

---

## Lancer le pipeline

```bash
export DATABASE_URL=postgresql://gpe:gpe@localhost:5432/gpe

make db-init       # Crée les schémas et tables
make ingest        # Télécharge et charge les données brutes
make dbt-run       # Transforme raw → staging → mart
make dbt-test      # Vérifie la qualité des données
```

Ou tout en une commande :

```bash
make all
```

---

## Tests

```bash
make test              # Tous les tests
make test-unit         # Tests unitaires uniquement
make test-integration  # Tests d'intégration uniquement
```

---

## Qualité du code

```bash
make lint       # Vérifie black, isort, flake8
make format     # Formate le code automatiquement
make typecheck  # Vérifie les types avec mypy
```

Les hooks pre-commit s'exécutent automatiquement à chaque `git commit`.

---

## Structure du projet

```
gpe/
├── ingestion/        # Scripts Python de téléchargement et chargement
├── dbt/              # Transformations SQL (staging + marts)
│   └── models/
│       ├── staging/  # Nettoyage et typage des données brutes
│       └── marts/    # Modèles analytiques finaux
├── tests/
│   ├── unit/         # Tests unitaires (parsing, transformations)
│   └── integration/  # Tests d'intégration (données en base)
├── docker-compose.yml
├── init.sql          # DDL : schémas, tables, extensions PostGIS
└── health_check.sql  # Requêtes d'audit de la base
```
