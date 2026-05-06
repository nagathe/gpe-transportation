-- =============================================================================
-- create_tables.sql
-- Initialisation du schéma raw pour le projet GPE
--
-- Usage :
--   psql $DATABASE_URL -f create_tables.sql
--
-- Convention :
--   - Toutes les tables sources atterrissent dans le schéma `raw`
--   - Les noms de colonnes INSEE sont conservés tels quels (casse originale)
--     pour faciliter la traçabilité avec la documentation INSEE
--   - Ce fichier est la référence du DDL : toute modification de schéma
--     passe d'abord ici, puis via un ALTER TABLE de migration si la table
--     existe déjà en production
--
-- NE PAS laisser pandas/SQLAlchemy gérer le DDL (if_exists="replace") :
--   cela rendrait le schéma opaque et casserait les vues dbt en aval
--
-- Stratégie initialisation vs migration :
--   - Ce fichier sert à initialiser la base from scratch (ex: nouvel env)
--     Il peut être rejoué entièrement sans risque sur une base vide
--   - En production, NE PAS rejouer ce fichier pour modifier le schéma :
--     créer à la place un fichier migrations/00X_description.sql avec
--     uniquement les ALTER TABLE nécessaires, pour ne pas perdre les données
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Schéma raw
-- Contient les données brutes telles qu'ingérées depuis les sources externes,
-- sans transformation métier. Les modèles dbt lisent depuis ce schéma.
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS raw;


-- =============================================================================
-- Table : raw.insee_communes
-- Source : INSEE – Dossier complet des communes (recensement)
--          https://www.insee.fr/fr/statistiques/5359146
-- Fréquence de mise à jour : annuelle
-- Grain : une ligne par commune (CODGEO)
-- Enrichissement : coordonnées géographiques ajoutées via geo.api.gouv.fr
-- =============================================================================
-- Réinitialisation complète de la table.
-- Le DROP est volontaire : ce fichier est conçu pour être rejoué en
-- initialisation (nouvel environnement, reset de dev). En production,
-- passer par un fichier migrations/00X_*.sql pour ne pas perdre les données.
DROP TABLE IF EXISTS raw.insee_communes CASCADE;

CREATE TABLE raw.insee_communes (

    -- -------------------------------------------------------------------------
    -- Identifiant
    -- -------------------------------------------------------------------------

    -- Code officiel géographique INSEE (ex: "75056" pour Paris,
    -- "92012" pour Boulogne-Billancourt). Clé naturelle de la table.
    "CODGEO" TEXT PRIMARY KEY,

    -- -------------------------------------------------------------------------
    -- Indicateurs fiscaux (millésime 2021, source : DGFiP via INSEE)
    -- -------------------------------------------------------------------------

    -- Revenu médian disponible par unité de consommation (en euros)
    -- Référence : D5 de la distribution des revenus du foyer fiscal
    "MED21" DOUBLE PRECISION,

    -- Taux de pauvreté à 60 % du revenu médian national (en %)
    -- Part des personnes sous le seuil de pauvreté dans la population totale
    "TP6021" DOUBLE PRECISION,

    -- Nombre de personnes appartenant à un ménage fiscal
    -- Utilisé comme proxy de la population couverte par les données fiscales
    "NBPERSMENFISC21" DOUBLE PRECISION,

    -- -------------------------------------------------------------------------
    -- Coordonnées géographiques
    -- Source : geo.api.gouv.fr (centroïde de la commune)
    -- Système de référence : WGS84 (EPSG:4326)
    -- -------------------------------------------------------------------------

    -- Longitude du centroïde de la commune (axe est-ouest)
    longitude DOUBLE PRECISION,

    -- Latitude du centroïde de la commune (axe nord-sud)
    latitude  DOUBLE PRECISION

);

-- Index géographique pour accélérer les requêtes spatiales
-- (filtres par bbox, jointures avec d'autres tables géolocalisées)
CREATE INDEX idx_insee_communes_geo
    ON raw.insee_communes (latitude, longitude);

-- Index sur le taux de pauvreté, souvent utilisé comme critère de filtrage
-- dans les modèles dbt et les dashboards
CREATE INDEX idx_insee_communes_tp6021
    ON raw.insee_communes ("TP6021");


-- =============================================================================
-- Fin du fichier
-- Pour ajouter une nouvelle table source, suivre le même modèle :
--   1. Documenter la source et le grain
--   2. Typer explicitement chaque colonne
--   3. Commenter les colonnes non évidentes
--   4. Créer les index utiles aux requêtes dbt
-- =============================================================================