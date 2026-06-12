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
--   - Les seuils de quartile_revenu sont calibrés sur la distribution IDF :
--       Q1 < 22 000 €  → communes très précaires (Seine-Saint-Denis, etc.)
--       Q2 < 27 000 €  → communes précaires
--       Q3 < 33 000 €  → communes dans la médiane IDF
--       Q4 ≥ 33 000 €  → communes aisées (Hauts-de-Seine ouest, etc.)
--   - profil_territoire est l'indicateur clé pour les visu finales
--   - 15 communes exclues car population < 1000 hab
--     (seuil de confidentialité Filosofi INSEE)
--     Communes concernées : très petites communes rurales 77/78/91/95
-- =============================================================================

with accessibilite as (
    -- Accessibilité actuelle + coordonnées géographiques
    select * from {{ ref('accessibilite_par_commune') }}
),

gain as (
    -- Gain GPE + taux_chomage déjà calculé + categorie_gain
    select * from {{ ref('gain_mobilite') }}
),

-- Enrichissement : on ajoute quartile_revenu à partir du revenu_median
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
        -- Quartile de revenu (classification sur seuils IDF)
        case
            when a.revenu_median < {{ var('seuil_revenu_q1') }} then 'Q1 - Très précaire'
            when a.revenu_median < {{ var('seuil_revenu_q2') }} then 'Q2 - Précaire'
            when a.revenu_median < {{ var('seuil_revenu_q3') }} then 'Q3 - Médian'
            else 'Q4 - Aisé'
        end as quartile_revenu
    from accessibilite a
    left join gain g using (code_commune)
    where a.revenu_median is not null
    -- Note : 15 communes exclues car population < 1000 hab
    -- (seuil de confidentialité Filosofi INSEE)
    -- Communes concernées : très petites communes rurales 77/78/91/95
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
from enrichi
