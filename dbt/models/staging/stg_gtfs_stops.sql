-- =============================================================================
-- STAGING : stg_gtfs_stops
-- =============================================================================
-- Objectif : Nettoyer et standardiser les arrêts de transport en commun IDFM
--            en casting les coordonnées et en créant la géométrie PostGIS.
--
-- Source   : raw.gtfs_stops (données GTFS Île-de-France)
--
-- Granularité : 1 ligne par zone d'arrêt (station), location_type = 1
--
-- Transformations :
--   - Conservation des seules zones d'arrêt (location_type = 1)
--   - Cast latitude/longitude en float (au cas où mal typées)
--   - Création colonne geom : géométrie PostGIS SRID 4326 (WGS84)
--   - Suppression arrêts incomplets (sans ID ou sans coordonnées valides)
--
-- Notes métier :
--   - Le GTFS décrit une même station sur plusieurs lignes : la zone d'arrêt
--     (location_type = 1), ses quais (0, un par direction ou par ligne) et ses
--     entrées/sorties (2). Compter toutes les lignes comptait chaque station
--     environ 3,6 fois et avantageait les grosses gares (ex. Châtelet : 1 zone
--     métro/RER pour 22 quais). On ne garde donc que les zones d'arrêt :
--     une station = un arrêt (décision #6, 17/11/2026).
--   - SRID 4326 (WGS84) standard pour les données géographiques Web
--   - Filtrage des NULLs strictement nécessaire pour les jointures spatiales
-- =============================================================================

with source as (
    select * from {{ source('raw', 'gtfs_stops') }}
)

select
    stop_id,
    stop_name,
    stop_lat::float,
    stop_lon::float,
    location_type,
    ST_SetSRID(ST_MakePoint(stop_lon::float, stop_lat::float), 4326) as geom
from source
where location_type = 1
  and stop_id is not null
  and stop_lat is not null
  and stop_lon is not null