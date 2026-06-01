-- models/staging/stg_gpe_gares.sql
with source as (
    select * from raw.gpe_gares_shapefile
),

cleaned as (
    select
        code_gare,
        nom_gare,
        ligne_gpe                           as ligne,
        interconnexion,
        latitude::double precision          as latitude,
        longitude::double precision         as longitude,
        geometry                            as geom,
        -- Nettoyage date
        nullif(trim(date_diffu), '')        as date_diffusion
    from source
    where nom_gare is not null
      and latitude is not null
      and longitude is not null
)

select * from cleaned
