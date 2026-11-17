-- =============================================================================
-- TEST : chaque quartile de revenu regroupe environ 25 % des habitants (#36)
-- =============================================================================
-- quartile_revenu doit être un vrai quartile d'habitants. Une commune entière
-- reste dans un seul groupe (Paris arrondissements, grandes villes) : on tolère
-- donc 20 % à 30 %. Le test échoue (renvoie des lignes) si un groupe sort de
-- cette plage, par exemple si on revenait à des seuils de revenu écrits à la main.
-- =============================================================================

with parts as (
    select
        quartile_revenu,
        sum(population) / sum(sum(population)) over () as part_habitants
    from {{ ref('precarite_vs_mobilite') }}
    group by quartile_revenu
)

select *
from parts
where part_habitants < 0.20 or part_habitants > 0.30
