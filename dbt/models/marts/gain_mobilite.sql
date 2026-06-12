-- =============================================================================
-- MART : gain_mobilite
-- =============================================================================
-- Objectif : Estimer le gain de mobilité apporté par le GPE par commune.
--            On croise les futures gares GPE avec l'accessibilité actuelle
--            pour catégoriser chaque commune selon son gain attendu.
--
-- Sources   : staging.stg_insee_communes
--             staging.stg_gpe_gares
--             marts.accessibilite_par_commune
--
-- Granularité : 1 ligne par commune INSEE
--
-- Modifications v2 :
--   - Ajout nom_commune, latitude, longitude, geom (propagés depuis accessibilite)
--   - Ajout taux_chomage (calculé ici, récupéré par precarite_vs_mobilite)
--
-- Notes métier :
--   - Rayon de 2km pour les gares GPE (vs 1km pour arrêts bus/métro)
--     car les gares GPE sont des nœuds structurants, pas des arrêts de proximité
--   - Les seuils de categorie_gain (10, 50 arrêts/10000 hab) sont calibrés
--     sur la distribution observée en IDF
--   - taux_chomage calculé ici une seule fois pour éviter la duplication
--     dans precarite_vs_mobilite
-- =============================================================================

with communes as (
    -- Toutes les communes Île-de-France avec leurs indicateurs socio-économiques
    select * from {{ ref('stg_insee_communes') }}
),

gpe_gares as (
    -- Futures gares du Grand Paris Express (lignes 15, 16, 17, 18)
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
            {{ var('rayon_gpe_metres') }}  -- zone d'influence d'une gare structurante
        )
    where c.longitude is not null and c.latitude is not null
    group by c.code_commune
),

accessibilite as (
    -- On hérite de tous les indicateurs calculés dans le mart amont
    -- notamment geom, nom_commune, arrets_pour_10000_hab
    select * from {{ ref('accessibilite_par_commune') }}
)

select
    a.code_commune,
    a.nom_commune,             -- propagé depuis accessibilite_par_commune
    a.population,
    a.revenu_median,
    a.nb_chomeurs,
    a.nb_actifs,
    a.latitude,                -- propagé depuis accessibilite_par_commune
    a.longitude,               -- propagé depuis accessibilite_par_commune
    a.geom,                    -- propagé depuis accessibilite_par_commune
    a.nb_arrets_actuels,
    a.arrets_pour_10000_hab,
    -- Taux de chômage calculé ici une seule fois
    -- récupéré tel quel par precarite_vs_mobilite (pas recalculé)
    round(
        (a.nb_chomeurs / nullif(a.nb_actifs, 0) * 100)::numeric,
        2
    ) as taux_chomage,
    coalesce(g.nb_gares_gpe, 0) as nb_gares_gpe_futures,
    -- Catégorisation du gain : croise présence GPE et niveau actuel de desserte
    -- Fort gain    = commune sous-desservie qui reçoit une gare GPE
    -- Gain modéré  = commune moyennement desservie qui reçoit une gare GPE
    -- Gain faible  = commune déjà bien desservie qui reçoit une gare GPE
    -- Pas de gare  = commune non concernée par le tracé GPE
    case
        when coalesce(g.nb_gares_gpe, 0) > 0 and a.arrets_pour_10000_hab < {{ var('seuil_sous_desserte') }}  then 'Fort gain'
        when coalesce(g.nb_gares_gpe, 0) > 0 and a.arrets_pour_10000_hab < {{ var('seuil_gain_modere') }}    then 'Gain modéré'
        when coalesce(g.nb_gares_gpe, 0) > 0                                    then 'Gain faible (déjà bien desservi)'
        else 'Pas de gare GPE'
    end as categorie_gain
from accessibilite a
left join gpe_par_commune g using (code_commune)
