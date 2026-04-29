-- Crée les schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Active PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Crée les tables brutes
CREATE TABLE IF NOT EXISTS raw.gtfs_stops (
    stop_id VARCHAR(50) PRIMARY KEY,
    stop_code VARCHAR(50),
    stop_name VARCHAR(255),
    stop_desc TEXT,
    stop_lat DECIMAL(10, 8),
    stop_lon DECIMAL(11, 8),
    location_type INT,
    parent_station VARCHAR(50),
    stop_timezone VARCHAR(50),
    wheelchair_boarding INT
);

CREATE TABLE IF NOT EXISTS raw.insee_communes (
    code_commune VARCHAR(10) PRIMARY KEY,
    nom_commune VARCHAR(255),
    population INT,
    revenu_median DECIMAL(10, 2),
    taux_chomage DECIMAL(5, 2),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8)
);

CREATE TABLE IF NOT EXISTS raw.gpe_gares (
    gare_id VARCHAR(50) PRIMARY KEY,
    gare_name VARCHAR(255),
    ligne VARCHAR(50),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    date_ouverture DATE
);

-- Crée les géométries
ALTER TABLE raw.gtfs_stops ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);
ALTER TABLE raw.insee_communes ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);
ALTER TABLE raw.gpe_gares ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);

-- Ajoute des index pour les performances
CREATE INDEX IF NOT EXISTS idx_gtfs_stops_geom ON raw.gtfs_stops USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_insee_communes_geom ON raw.insee_communes USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_gpe_gares_geom ON raw.gpe_gares USING GIST(geom);
