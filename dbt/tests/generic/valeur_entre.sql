-- =============================================================================
-- TEST GÉNÉRIQUE : valeur_entre (#29)
-- =============================================================================
-- Vérifie qu'une colonne reste dans une plage [min_value, max_value].
-- Le projet n'utilise pas dbt_utils : ce test maison remplace son
-- accepted_range, sans ajouter de dépendance.
--
-- Fonctionnement :
--   - renvoie les lignes HORS plage : le test échoue s'il en trouve au moins une ;
--   - les NULL sont acceptés (à combiner avec not_null si la colonne est
--     obligatoire) ;
--   - min_value et max_value sont facultatifs : on peut ne donner qu'une borne.
--
-- Utilisation dans un schema.yml :
--   data_tests:
--     - valeur_entre:
--         min_value: 0
--         max_value: 1
-- =============================================================================

{% test valeur_entre(model, column_name, min_value=none, max_value=none) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and (
      false
      {% if min_value is not none %} or {{ column_name }} < {{ min_value }} {% endif %}
      {% if max_value is not none %} or {{ column_name }} > {{ max_value }} {% endif %}
  )

{% endtest %}
