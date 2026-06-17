-- =============================================================================
-- STAGING : stg_gtfs_stops
-- =============================================================================
-- Objectif : Nettoyer et standardiser les arrêts de transport en commun IDFM
--            en casting les coordonnées et en créant la géométrie PostGIS.
--
-- Source   : raw.gtfs_stops (données GTFS Île-de-France)
--
-- Granularité : 1 ligne par arrêt unique (stop_id)
--
-- Transformations :
--   - Cast latitude/longitude en float (au cas où mal typées)
--   - Création colonne geom : géométrie PostGIS SRID 4326 (WGS84)
--   - Suppression arrêts incomplets (sans ID ou sans coordonnées valides)
--
-- Notes métier :
--   - SRID 4326 (WGS84) standard pour les données géographiques Web
--   - Filtrage des NULLs strictement nécessaire pour les jointures spatiales
-- =============================================================================

with source as (
    select * from raw.gtfs_stops
)

select
    stop_id,
    stop_name,
    stop_lat::float,
    stop_lon::float,
    ST_SetSRID(ST_MakePoint(stop_lon::float, stop_lat::float), 4326) as geom
from source
where stop_id is not null
  and stop_lat is not null
  and stop_lon is not null