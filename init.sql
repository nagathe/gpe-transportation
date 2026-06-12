-- Crée les schémas utilisés par le pipeline
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;

-- Active PostGIS (nécessite superuser)
CREATE EXTENSION IF NOT EXISTS postgis CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis_topology CASCADE;

-- ===== GTFS =====
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

CREATE TABLE IF NOT EXISTS raw.gtfs_routes (
    route_id TEXT,
    agency_id TEXT,
    route_short_name TEXT,
    route_long_name TEXT,
    route_desc TEXT,
    route_type TEXT,
    route_url TEXT,
    route_color TEXT,
    route_text_color TEXT
);

CREATE TABLE IF NOT EXISTS raw.gtfs_trips (
    route_id TEXT,
    service_id TEXT,
    trip_id TEXT,
    trip_headsign TEXT,
    trip_short_name TEXT,
    direction_id TEXT,
    block_id TEXT,
    shape_id TEXT,
    wheelchair_accessible TEXT,
    bikes_allowed TEXT
);

CREATE TABLE IF NOT EXISTS raw.gtfs_stop_times (
    trip_id TEXT,
    arrival_time TEXT,
    departure_time TEXT,
    stop_id TEXT,
    stop_sequence TEXT,
    stop_headsign TEXT,
    pickup_type TEXT,
    drop_off_type TEXT,
    shape_dist_traveled TEXT,
    timepoint TEXT
);

-- ===== INSEE COMMUNES =====
CREATE TABLE IF NOT EXISTS raw.insee_communes (
    code_commune TEXT PRIMARY KEY,
    population DOUBLE PRECISION,
    revenu_median DOUBLE PRECISION,
    nb_chomeurs DOUBLE PRECISION,
    nb_actifs DOUBLE PRECISION,
    nb_menages DOUBLE PRECISION,
    taux_chomage DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_insee_communes_geo
    ON raw.insee_communes (latitude, longitude);

CREATE INDEX IF NOT EXISTS idx_insee_communes_revenu_median
    ON raw.insee_communes (revenu_median);

CREATE INDEX IF NOT EXISTS idx_insee_communes_taux_chomage
    ON raw.insee_communes (taux_chomage);

-- ===== COMMUNE NAMES =====
CREATE TABLE IF NOT EXISTS raw.commune_names (
    code_commune TEXT PRIMARY KEY,
    nom_commune TEXT
);

CREATE INDEX IF NOT EXISTS idx_commune_names_nom_commune
    ON raw.commune_names (nom_commune);

-- ===== GPE GARES =====
CREATE TABLE IF NOT EXISTS raw.gpe_gares (
    nom_gare TEXT,
    ligne_gpe TEXT,
    interconnexion TEXT,
    source TEXT,
    geometry GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS idx_gpe_gares_geometry
    ON raw.gpe_gares USING GIST (geometry);

CREATE INDEX IF NOT EXISTS idx_gpe_gares_ligne_gpe
    ON raw.gpe_gares (ligne_gpe);

-- Les géométries analytiques GTFS sont construites dans dbt/models/staging.
