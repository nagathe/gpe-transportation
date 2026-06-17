-- =============================================================================
-- STAGING : stg_insee_communes
-- =============================================================================
-- Objectif : Nettoyer et enrichir les indicateurs socio-économiques INSEE
--            en joignant les noms de communes depuis GeoAPI.
--
-- Sources  : raw.insee_communes (données INSEE par commune)
--            raw.commune_names (référence noms communes depuis GeoAPI)
--
-- Granularité : 1 ligne par commune Île-de-France
--
-- Transformations :
--   - Join avec les noms de communes (GeoAPI) pour lisibilité
--   - Suppression communes sans code INSEE valide
--   - Sélection colonnes clés : code, nom, population, revenus, chômage, géographie
--
-- Notes métier :
--   - taux_chomage pré-calculé en raw.insee_communes (nb_chomeurs / nb_actifs)
--   - distinct on utilisé pour éviter les doublons de communes (cas des arrondissements Paris)
-- =============================================================================

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