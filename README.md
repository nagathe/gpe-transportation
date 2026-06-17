# Grand Paris Express — Pipeline Data

**Problématique posée :** Le Grand Paris Express va-t-il réduire les inégalités de mobilité en banlieue ?

Ce projet mesure, commune par commune en Île-de-France, qui gagne en accessibilité avec le GPE —
et si ce sont bien les zones les plus précaires qui en bénéficient le plus.

---

## Architecture

```
Ingestion (Python)        Staging (dbt views)           Marts (dbt tables)
─────────────────         ───────────────────           ──────────────────
fetch_gtfs.py            →  stg_gtfs_stops             →  accessibilite_par_commune
fetch_insee.py           →  stg_insee_communes         →  gain_mobilite
fetch_gpe.py             →  stg_gpe_gares              →  precarite_vs_mobilite
```

**Sources de données :**
- GTFS IDFM — réseau de transport actuel (arrêts, lignes)
- INSEE — revenus, chômage, population par commune IDF
- Shapefile SdGP — futures gares GPE (lignes 15/16/17/18)


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
├── db/               # Fichiers DDL et scripts d'audit
│   ├── init.sql      # DDL : schémas, tables, extensions PostGIS
│   └── health_check.sql  # Requêtes d'audit de la base
├── grafana/          # Dashboards de visualisation
│   ├── dashboards/   # Fichiers JSON des dashboards Grafana
│   └── queries/      # Requêtes SQL pour référence
├── docker-compose.yml
└── pytest.ini        # Configuration pytest
```

---

## Installation

### Prérequis
- Docker Desktop
- Python 3.11+
- Git
- Make (ou utiliser les commandes Docker directement)

### 1. Configurer l'environnement

```bash
cp .env.exemple .env
```

Ensuite édite `.env` pour ajouter ta clé API IDFM :

```bash
nano .env
# Remplacer YOUR_API_KEY_HERE par ta clé IDFM
```

**Obtenir les clés :**
- **IDFM_API_KEY** : Inscription sur https://prim.iledefrance-mobilites.fr/ (gratuit)
- **POSTGRES_PASSWORD** : Personnaliser si souhaité (défaut : `gpe`)
- **GRAFANA_ADMIN_PASSWORD** : Personnaliser si souhaité (défaut : `admin`)

Les autres valeurs (POSTGRES_USER, POSTGRES_DB, GRAFANA_ADMIN_USER) peuvent rester par défaut.

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
| Grafana    | http://localhost:3000 |
| PostgreSQL | localhost:5432        |

### 4. Vérifier l'installation

```bash
# Vérifier que PostgreSQL est accessible
psql -h localhost -U gpe -d gpe -c "SELECT version();"

# Vérifier que Grafana répond
curl http://localhost:3000/api/health
```

Si tout fonctionne :
- PostgreSQL affiche sa version
- Grafana répond avec `{"status":"ok"}`

### Commandes Makefile

| Commande | Effet |
|----------|-------|
| `make all` | Lance tout le pipeline (init + ingest + dbt) |
| `make db-init` | Initialise les schémas et tables |
| `make ingest` | Télécharge et charge les données brutes |
| `make dbt-run` | Exécute les transformations dbt |
| `make dbt-test` | Valide les données dbt |
| `make test` | Lance tous les tests (unit + integration) |
| `make lint` | Vérifie le style du code |
| `make format` | Formate automatiquement le code |
| `make docker-up` | Démarre PostgreSQL + Grafana |
| `make docker-down` | Arrête les services |

### Architecture Docker

Le projet utilise Docker Compose pour isoler et versioner les dépendances d'infrastructure :

- **PostgreSQL 15 + PostGIS** : Base de données avec extension géospatiale (pour les coordonnées des gares/communes)
- **Grafana 10.3.1** : Dashboards de visualisation des données


**Commandes utiles :**
```bash
make docker-up       # Démarre PostgreSQL + Grafana
make docker-down     # Arrête les services (conserve les données)
make docker-clean    # Supprime les volumes (⚠️ perte de données)
docker ps            # Vérifie les services actifs
docker logs postgres # Logs PostgreSQL
docker logs grafana  # Logs Grafana
```

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

**⚠️ Note sur l'ingestion :** Les téléchargements externes (INSEE, GTFS, GPE) prennent **10-15 minutes** selon la connexion. Ne pas interrompre.

---

## Tests

```bash
make test              # Tous les tests
make test-unit         # Tests unitaires uniquement
make test-integration  # Tests d'intégration uniquement
```

---

## Visualisation : Dashboard Grafana

**URL :** http://localhost:3000  
Connexion par défaut : `admin` / `admin`

### Importer le dashboard

1. Ouvrir Grafana → Home → New → Import
2. Copier-coller le contenu de `grafana/dashboards/gpe-inegalites-mobilite.json`
3. Sélectionner `PostgreSQL` comme datasource
4. Cliquer sur Import

### Dashboard : "GPE — Les inégalités de mobilité vont-elles diminuer ?"

**Question centrale répondue :** Le GPE aide-t-il plus les communes pauvres que les riches ?

**6 panels — ce qu'ils montrent :**

| Panel | Visualisation | Question répondue | Données clés |
|-------|---------------|-------------------|--------------|
| **Distribution par desserte** | Pie chart | Quelle est la situation actuelle ? | Communes classées en 4 catégories (très mal / mal / moyen / bien desservies) |
| **Accessibilité par revenu** | Bar chart | Y a-t-il une inégalité actuelle ? | Moyenne d'arrêts/10k hab par quartile (Q1=pauvre→23.5, Q4=riche→88.8) |
| **% aidées par GPE** | Bar chart | Qui bénéficie le plus ? | % communes avec future gare GPE : Q1=31.5%, Q4=7.37% |
| **% Pauvres aidés** | Stat | Combien de communes pauvres gagnent ? | 31.5% des communes Q1 auront une gare GPE |
| **% Riches aidés** | Stat | Combien de communes riches gagnent ? | 7.69% des communes Q4 auront une gare GPE |
| **Écart d'aide** | Stat | **Verdict final** | 31.5% - 7.69% = **+23.8 points → GPE aide plus les pauvres** ✓ |

**Résultat :** Le GPE **réduit les inégalités** en ciblant les communes pauvres et mal desservies.

---

## Qualité du code

```bash
make lint       # Vérifie black, isort, flake8
make format     # Formate le code automatiquement
make typecheck  # Vérifie les types avec mypy
```

Les hooks pre-commit s'exécutent automatiquement à chaque `git commit`.

---

## CI/CD

**GitHub Actions** s'exécute automatiquement sur chaque push/PR vers `master`.

### Pipeline

| Étape | Commande | Objectif |
|-------|----------|----------|
| **black** | Formatage du code | Vérifie que le code suit les règles de style |
| **isort** | Tri des imports | Organise les imports automatiquement |
| **mypy** | Typage statique | Détecte les erreurs de types |
| **pytest (unit)** | Tests unitaires | Valide les transformations, parsing, etc. |

### Tests d'intégration

Les tests d'intégration (qui nécessitent une vraie DB PostgreSQL) s'exécutent **localement** avant merge :

```bash
make test-integration
```

Raison : les tests d'intégration dépendent de téléchargements externes (INSEE, GTFS, GPE) qui sont fragiles en CI.

---

## Troubleshooting

### ❌ Le port 5432 est déjà utilisé

```bash
# Trouver le processus qui occupe le port
lsof -i :5432

# Ou utiliser un port différent
docker-compose -f docker-compose.yml up -d postgres -e POSTGRES_PORT=5433
```

### ❌ PostgreSQL ne démarre pas

```bash
# Voir les logs
docker logs postgres

# Supprimer le volume et relancer
make docker-clean
make docker-up
```

### ❌ "Cannot connect to database"

```bash
# Vérifier que PostgreSQL est running
docker ps | grep postgres

# Vérifier la connexion
psql -h localhost -U gpe -d gpe -c "SELECT 1"
```

### ❌ Ingest échoue (téléchargements bloqués)

- INSEE et GTFS peuvent être temporairement indisponibles
- Relancer avec `make ingest` après quelques minutes
- Vérifier votre connexion internet

### ❌ dbt échoue

```bash
# Réinstaller les dépendances
pip install -r requirements.txt --force-reinstall

# Relancer dbt
make dbt-run
```

---

