# Projet Pipeline Data : Grand Paris Express
***Répondre à la problématique suivante :***
Le Grand Paris Express va-t-il réduire les inégalités de mobilité en banlieue ?
off the rec : mesure de qui gagne quoi en accessibilité avec le GPE, et est-ce que ce sont les zones les plus précaires qui en bénéficient le plus ?


## 1. Installation

```bash
pip install pre-commit
pre-commit install
```

**Outils**
- black : formatage automatique du code
- flake8 : détection d'erreurs de style
- isort : tri des imports


## 2. Lancer le projet

### 2.1 Prérequis
- Docker Desktop installé et **démarré**
- Python 3.11+

### 2.2 Démarrer les services

#### Ouvrir Docker Desktop puis :
```bash
docker compose up -d
```

#### Vérifier que tout tourne
```bash
docker ps
```

#### Services disponibles :

| Services | URL |
|-----------|-----------|
| Airflow | http://localhost:8080 |
| Grafana | http://localhost:3000 |
| PostgreSQL | http://localhost:5432 |


### 2.3 Initialiser la base de données
```bash
docker exec -it gpe-postgres-1 psql -U gpe -d gpe -c "CREATE DATABASE gpe_test;"
```

### 2.4 Installer les dépendances Python
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2.5 Lancement du pipeline
##### Lancement de l'ingestion
##### Lancement du chargement
##### Lancement du traitement et des transormations


## 3. Qualité du code

Les hooks pre-commit sont configurés pour s'exécuter à chaque `git commit`

### 3.1 Lancer les tests
```bash
export DATABASE_URL_TEST="postgresql://gpe:gpe@localhost:5432/gpe_test"
pytest tests/ -v
```




### divers notes 
75056 = Paris entier (2M habitants, 277 arrêts) ✅
75101-75104 = arrondissements de Paris avec 0 arrêts — c'est normal, le GTFS regroupe tout sur le code commune Paris (75056)
Source GPE : shapefile SdGP 2016 — 54 gares (lignes 15/16/17/18)
Données partielles : tracé définitif non reflété pour L16/L17/L18

### explications des marts 
Dans une architecture ELT, les données passent par trois couches : Raw (données brutes), Staging (nettoyage et typage), Mart (modèles analytiques finaux).
Le dossier mart est la couche finale. C'est ici qu'on répond aux questions métier du projet, avec trois modèles :

accessibilite_par_commune — nombre d'arrêts de transport actuels dans un rayon de 2 km par commune. La photographie de la mobilité aujourd'hui.
gain_mobilite — nombre de futures gares GPE à moins de 2 km par commune, avec une catégorisation (fort gain / modéré / aucun).
precarite_vs_mobilite — croisement mobilité × données INSEE (revenu médian, chômage). C'est le cœur de la question du projet : le GPE bénéficie-t-il aux communes qui en ont le plus besoin ?

Ces trois tables alimentent directement les dashboards. Tout le travail analytique est fait ici, en SQL versionné dans Git, de façon traçable et reproductible.