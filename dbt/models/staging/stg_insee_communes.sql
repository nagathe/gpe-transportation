with source as (
    select * from raw.insee_communes
)

select
    "CODGEO"                as code_commune,
    "MED21"                 as revenu_median,
    "TP6021"                as taux_pauvrete,
    "NBPERSMENFISC21"       as nb_personnes_fiscales
from source
where "CODGEO" is not null
