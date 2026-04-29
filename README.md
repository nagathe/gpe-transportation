## Qualité du code

Les hooks pre-commit sont configurés pour s'exécuter à chaque `git commit`.

### Installation

```bash
pip install pre-commit
pre-commit install
Outils

black : formatage automatique du code
flake8 : détection d'erreurs de style
isort : tri des imports
```

# Lancer le projet

### Prérequis
- Docker Desktop installé et **démarré**
- Python 3.11+

### 1. Démarrer les services

#### Ouvrir Docker Desktop puis :
```bash
docker compose up -d
```

#### Vérifier que tout tourne
```bash
docker ps
```

#### Services disponibles :
Services        URL
Airflow         http://localhost:8080
Grafana         http://localhost:3000
PostgreSQL      localhost:5432


### 2. Initialiser la base de données
```bash
docker exec -it gpe-postgres-1 psql -U gpe -d gpe -c "CREATE DATABASE gpe_test;"
```

### 3. Installer les dépendances Python
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Lancer les tests
```bash
export DATABASE_URL_TEST="postgresql://gpe:gpe@localhost:5432/gpe_test"
pytest tests/ -v
```
