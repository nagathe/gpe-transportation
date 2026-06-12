with source as (
    select * from raw.insee_communes
),

ref as (
    select distinct on (code_commune)
        code_commune,
        nom_commune
    from raw.commune_names
    order by code_commune
)

select
    s.code_commune,
    r.nom_commune,
    s.population,
    s.revenu_median,
    s.nb_chomeurs,
    s.nb_actifs,
    s.nb_menages,
    s.taux_chomage,
    s.longitude,
    s.latitude
from source s
left join ref r on r.code_commune = s.code_commune
where s.code_commune is not null