-- =============================================================================
-- MART : precarite_vs_mobilite
-- =============================================================================
-- Objectif : Croiser précarité socio-économique et accessibilité transport
--            pour répondre à la question centrale du projet :
--            "Le GPE cible-t-il les zones les plus précaires ?"
--
-- Sources   : marts.accessibilite_par_commune
--             marts.gain_mobilite
--
-- Granularité : 1 ligne par commune INSEE
--
-- Modifications v2 :
--   - Ajout nom_commune, latitude, longitude, geom (propagés depuis amont)
--   - taux_chomage récupéré depuis gain_mobilite (plus recalculé ici)
--
-- Notes métier :
--   - quartile_revenu = vrais quartiles d'HABITANTS (#36) : on range les
--     communes du revenu médian le plus bas au plus haut et on cumule leur
--     population. Q1 = communes où vit le quart le plus pauvre des Franciliens
--     (part cumulée <= 25 %), Q2 <= 50 %, Q3 <= 75 %, Q4 le reste.
--     Chaque groupe compte donc environ le même nombre d'habitants. Les bornes
--     sont calculées sur les données, pas écrites à la main (au 17/11/2026 :
--     ~23 970 / 28 400 / 34 270 €). Remplace les anciens seuils fixes
--     22 000 / 27 000 / 33 000 €, qui donnaient des groupes très inégaux
--     (2,1 M d'habitants en Q1 contre 3,7 M en Q3).
--   - profil_territoire est l'indicateur clé pour les visu finales
--   - 14 communes exclues car leur revenu_median est NULL : l'INSEE ne le
--     diffuse pas (secret statistique Filosofi). Ce sont de très petites
--     communes rurales (77/78/91/95, 102 habitants au plus).
-- =============================================================================

with accessibilite as (
    -- Accessibilité actuelle + coordonnées géographiques
    select * from {{ ref('accessibilite_par_commune') }}
),

gain as (
    -- Gain GPE + taux_chomage déjà calculé + categorie_gain
    select * from {{ ref('gain_mobilite') }}
),

-- Enrichissement : on ajoute la part cumulée d'habitants, base de quartile_revenu
enrichi as (
    select
        a.code_commune,
        a.nom_commune,             -- propagé pour lisibilité des visu
        a.population,
        a.revenu_median,
        a.latitude,                -- propagé pour les cartes
        a.longitude,               -- propagé pour les cartes
        a.geom,                    -- propagé pour les cartes
        a.nb_arrets_actuels,
        a.arrets_pour_10000_hab,
        g.nb_gares_gpe_futures,
        g.categorie_gain,
        g.taux_chomage,            -- récupéré depuis gain_mobilite, pas recalculé
        -- Part des Franciliens vivant dans une commune au revenu médian
        -- inférieur ou égal (calculée après le filtre revenu_median non NULL)
        sum(a.population) over (
            order by a.revenu_median, a.code_commune
            rows between unbounded preceding and current row
        ) / sum(a.population) over () as part_habitants_cumulee
    from accessibilite a
    left join gain g using (code_commune)
    where a.revenu_median is not null
    -- Exclut les 14 communes au revenu non diffusé par l'INSEE (voir en-tête)
),

-- Quartile d'habitants (voir en-tête)
avec_quartile as (
    select
        *,
        case
            when part_habitants_cumulee <= 0.25 then 'Q1 - Très précaire'
            when part_habitants_cumulee <= 0.50 then 'Q2 - Précaire'
            when part_habitants_cumulee <= 0.75 then 'Q3 - Médian'
            else 'Q4 - Aisé'
        end as quartile_revenu
    from enrichi
)

select
    *,
    -- Score de vulnérabilité combiné : précarité + faible mobilité
    -- C'est l'indicateur central de la problématique du projet
    -- "Territoire oublié"      = précaire + mal desservi + pas de GPE → alerte rouge
    -- "Territoire ciblé GPE"   = précaire + GPE prévu → le GPE fait son travail
    -- "Territoire aisé GPE"    = aisé + GPE prévu → bénéfice pour zones déjà favorisées
    -- "Territoire standard"    = tous les autres cas
    case
        when quartile_revenu in ('Q1 - Très précaire', 'Q2 - Précaire')
             and arrets_pour_10000_hab < {{ var('seuil_sous_desserte') }}
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
from avec_quartile
