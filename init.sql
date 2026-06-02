-- Crée les schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Active PostGIS (nécessite superuser)
CREATE EXTENSION IF NOT EXISTS postgis CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis_topology CASCADE;

-- ===== GTFS STOPS =====
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
    wheelchair_boarding INT,
    geom GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS idx_gtfs_stops_geom ON raw.gtfs_stops USING GIST(geom);

-- ===== INSEE COMMUNES =====
CREATE TABLE IF NOT EXISTS raw.insee_communes (
    "CODGEO" TEXT PRIMARY KEY,
    "MED21" DOUBLE PRECISION,
    "TP6021" DOUBLE PRECISION,
    "NBPERSMENFISC21" DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    geom GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS idx_insee_communes_geo ON raw.insee_communes (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_insee_communes_tp6021 ON raw.insee_communes ("TP6021");
CREATE INDEX IF NOT EXISTS idx_insee_communes_geom ON raw.insee_communes USING GIST(geom);

-- ===== GPE GARES =====
CREATE TABLE IF NOT EXISTS raw.gpe_gares (
    gare_id VARCHAR(50) PRIMARY KEY,
    gare_name VARCHAR(255),
    ligne VARCHAR(50),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    date_ouverture DATE,
    geom GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS idx_gpe_gares_geom ON raw.gpe_gares USING GIST(geom);

-- ===== POPULATE GEOMETRIES =====
-- Les scripts Python doivent mettre à jour ces colonnes geom,
-- mais on peut aussi le faire ici après l'ingestion avec :
-- UPDATE raw.gtfs_stops SET geom = ST_SetSRID(ST_Point(stop_lon, stop_lat), 4326) WHERE geom IS NULL;
