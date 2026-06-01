-- =============================================================================
-- MART : accessibilite_par_commune
-- =============================================================================
-- Objectif : Calculer le niveau d'accessibilité actuel de chaque commune
--            en comptant le nombre d'arrêts de transport en commun
--            dans un rayon de 1km autour du centre de la commune.
--
-- Sources   : staging.stg_insee_communes
--             staging.stg_gtfs_stops
--
-- Granularité : 1 ligne par commune INSEE
--
-- Notes métier :
--   - Le rayon de 1km est une convention standard pour l'accessibilité piétonne
--   - On utilise ::geography pour un calcul de distance en mètres (pas en degrés)
--   - arrets_pour_10000_hab permet de comparer des communes de tailles différentes
-- =============================================================================

with communes as (
    -- Toutes les communes Île-de-France avec leurs indicateurs socio-économiques
    select * from {{ ref('stg_insee_communes') }}
),

stops as (
    -- Tous les arrêts de transport en commun actuels (réseau IDFM)
    select * from {{ ref('stg_gtfs_stops') }}
),

stops_par_commune as (
    select
        c.code_commune,
        c.population,
        c.revenu_median,
        c.nb_chomeurs,
        c.nb_actifs,
        -- Jointure spatiale : on compte les arrêts dans un rayon de 1km
        -- autour du centroïde de chaque commune
        count(s.stop_id) as nb_arrets_actuels
    from communes c
    left join stops s
        on st_dwithin(
            st_makepoint(c.longitude, c.latitude)::geography,
            st_makepoint(s.stop_lon, s.stop_lat)::geography,
            1000  -- 1000 mètres = seuil piéton standard
        )
    group by
        c.code_commune,
        c.population,
        c.revenu_median,
        c.nb_chomeurs,
        c.nb_actifs
)

select
    code_commune,
    population,
    revenu_median,
    nb_chomeurs,
    nb_actifs,
    nb_arrets_actuels,
    -- Indicateur normalisé pour comparer communes de tailles différentes
    -- Ex : une commune de 10 000 hab avec 5 arrêts = 5.0
    case
        when population > 0
        then round(((nb_arrets_actuels::numeric / population) * 10000)::numeric, 2)
        else 0
    end as arrets_pour_10000_hab
from stops_par_commune
