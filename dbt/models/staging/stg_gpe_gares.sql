with source as (
    select * from raw.gpe_gares
)

select
    nom_gare,
    ligne,
    mise_en_service,
    statut,
    latitude,
    longitude,
    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) as geom
from source
where nom_gare is not null
  and latitude is not null
  and longitude is not null
