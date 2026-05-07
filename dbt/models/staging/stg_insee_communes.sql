with source as (
    select * from raw.insee_communes
)

select
    "CODGEO"            as code_commune,
    "P22_POP"           as population,
    "MED_SL23"          as revenu_median,
    "P22_CHOM1564"      as chomeurs,
    "P22_ACT1564"       as actifs,
    "C22_PMEN"          as nb_menages,
    longitude,
    latitude
from source
where "CODGEO" is not null
