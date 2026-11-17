-- =============================================================================
-- TEST : taux_chomage est un ratio entre 0 et 1 partout (#8)
-- =============================================================================
-- Le taux est calculé une seule fois à l'ingestion (nb_chomeurs / nb_actifs)
-- et stocké en 0-1 (8,7 % = 0,087). Ce test échoue (renvoie des lignes) si
-- une valeur sort de [0, 1], par exemple si quelqu'un remultiplie par 100.
-- Les NULL sont acceptés : nb_actifs nul ou manquant.
-- =============================================================================

select 'stg_insee_communes' as modele, code_commune, taux_chomage
from {{ ref('stg_insee_communes') }}
where taux_chomage < 0 or taux_chomage > 1

union all

select 'gain_mobilite', code_commune, taux_chomage
from {{ ref('gain_mobilite') }}
where taux_chomage < 0 or taux_chomage > 1

union all

select 'precarite_vs_mobilite', code_commune, taux_chomage
from {{ ref('precarite_vs_mobilite') }}
where taux_chomage < 0 or taux_chomage > 1
