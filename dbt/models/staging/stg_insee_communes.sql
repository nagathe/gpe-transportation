-- models/staging/stg_insee_communes.sql

with source as (
    select * from raw.insee_communes
),

noms as (
    select * from raw.commune_names
)

select
    source."CODGEO"         as code_commune,
    noms.nom_commune,
    source."P22_POP"        as population,
    source."MED_SL23"       as revenu_median,
    source."P22_CHOM1564"   as nb_chomeurs,
    source."P22_ACT1564"    as nb_actifs,
    source."C22_PMEN"       as nb_menages,
    -- Taux de chômage calculé ici une fois pour toutes
    case
        when source."P22_ACT1564" > 0
        then round(
            (source."P22_CHOM1564" / source."P22_ACT1564" * 100)::numeric, 2
        )
        else null
    end                     as taux_chomage,
    source.longitude,
    source.latitude
from source
left join noms
    on source."CODGEO" = noms.code_commune
where source."CODGEO" is not null
