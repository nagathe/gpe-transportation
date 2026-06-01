-- Croise précarité socio-économique et accessibilité transport
-- Permet de répondre : le GPE cible-t-il les zones précaires ?
with accessibilite as (
    select * from {{ ref('accessibilite_par_commune') }}
),

gain as (
    select * from {{ ref('gain_mobilite') }}
),

-- Calcul du taux de chômage
enrichi as (
    select
        a.code_commune,
        a.population,
        a.revenu_median,
        a.nb_arrets_actuels,
        a.arrets_pour_10000_hab,
        g.nb_gares_gpe_futures,
        g.categorie_gain,
        -- Taux de chômage en %
        round(
            (a.nb_chomeurs / nullif(a.nb_actifs, 0) * 100)::numeric,
            2
        ) as taux_chomage,
        -- Quartile de revenu (classification manuelle sur seuils IDF)
        case
            when a.revenu_median < 22000 then 'Q1 - Très précaire'
            when a.revenu_median < 27000 then 'Q2 - Précaire'
            when a.revenu_median < 33000 then 'Q3 - Médian'
            else 'Q4 - Aisé'
        end as quartile_revenu
    from accessibilite a
    left join gain g using (code_commune)
    where a.revenu_median is not null
)

select
    *,
    -- Score de vulnérabilité combiné : précarité + faible mobilité
    case
        when quartile_revenu in ('Q1 - Très précaire', 'Q2 - Précaire')
             and arrets_pour_10000_hab < 10
             and nb_gares_gpe_futures = 0
        then 'Territoire oublié'
        when quartile_revenu in ('Q1 - Très précaire', 'Q2 - Précaire')
             and nb_gares_gpe_futures > 0
        then 'Territoire ciblé par GPE'
        when quartile_revenu in ('Q3 - Médian', 'Q4 - Aisé')
             and nb_gares_gpe_futures > 0
        then 'Territoire aisé avec GPE'
        else 'Territoire standard'
    end as profil_territoire
from enrichi
