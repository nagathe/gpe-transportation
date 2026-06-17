-- =============================================================================
-- STAGING : stg_gpe_gares
-- =============================================================================
-- Objectif : Standardiser et géoréférencer les futures gares du Grand Paris Express
--            en extrayant coordonnées de la géométrie shapefile.
--
-- Source   : raw.gpe_gares (données shapefile GPE via data.gouv)
--
-- Granularité : 1 ligne par gare GPE future (lignes 15, 16, 17, 18)
--
-- Transformations :
--   - Renommage ligne_gpe → ligne pour cohérence
--   - Extraction latitude/longitude de la géométrie (ST_Y, ST_X)
--   - Alias geometry → geom (convention marts)
--   - Suppression gares sans nom valide
--
-- Notes métier :
--   - Géométries proviennent du shapefile GPE (projections géodésiques)
--   - ST_Y/ST_X extraient les coordonnées dans SRID d'origine du shapefile
--   - Seules les 4 lignes GPE sont concernées (15, 16, 17, 18)
-- =============================================================================

with source as (
    select * from raw.gpe_gares
),

cleaned as (
    select
        nom_gare,
        ligne_gpe       as ligne,
        interconnexion,
        geometry        as geom,
        st_y(geometry)  as latitude,
        st_x(geometry)  as longitude
    from source
    where nom_gare is not null
)

select * from cleaned
