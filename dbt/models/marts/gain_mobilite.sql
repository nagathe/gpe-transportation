-- Estimation du gain de mobilité apporté par le GPE par commune
-- On croise les arrêts GPE futurs avec l'accessibilité actuelle
with communes as (
    select * from {{ ref('stg_insee_communes') }}
),

gpe_gares as (
    select * from {{ ref('stg_gpe_gares') }}
),

-- Compte les futures gares GPE à moins de 2km du centroïde de chaque commune
gpe_par_commune as (
    select
        c.code_commune,
        count(g.nom_gare) as nb_gares_gpe  -- nom_gare est la clé dans stg_gpe_gares
    from communes c
    left join gpe_gares g
        on st_dwithin(
            st_makepoint(c.longitude, c.latitude)::geography,
            g.geom::geography,
            2000
        )
    where c.longitude is not null and c.latitude is not null
    group by c.code_commune
),


accessibilite as (
    select * from {{ ref('accessibilite_par_commune') }}
)

select
    a.code_commune,
    a.population,
    a.revenu_median,
    a.nb_chomeurs,
    a.nb_actifs,
    a.nb_arrets_actuels,
    a.arrets_pour_10000_hab,
    coalesce(g.nb_gares_gpe, 0) as nb_gares_gpe_futures,
    case
        when coalesce(g.nb_gares_gpe, 0) > 0 and a.arrets_pour_10000_hab < 10 then 'Fort gain'
        when coalesce(g.nb_gares_gpe, 0) > 0 and a.arrets_pour_10000_hab < 50 then 'Gain modéré'
        when coalesce(g.nb_gares_gpe, 0) > 0 then 'Gain faible (déjà bien desservi)'
        else 'Pas de gare GPE'
    end as categorie_gain
from accessibilite a
left join gpe_par_commune g using (code_commune)
