with source as (
    select * from raw.insee_communes
)

select
    code_commune,
    population,
    revenu_median,
    nb_chomeurs,
    nb_actifs,
    nb_menages,
    taux_chomage,
    longitude,
    latitude
from source
where code_commune is not null
