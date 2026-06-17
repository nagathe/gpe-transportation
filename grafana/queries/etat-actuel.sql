-- ============================================================================
-- État actuel des inégalités de mobilité en Île-de-France
-- ============================================================================
-- Analyse : Qui est mal desservi aujourd'hui ? Y a-t-il une corrélation
-- entre précarité et accessibilité ?

-- Q1: Communes mal desservies (< 10 arrêts/10k hab)
SELECT
    code_commune,
    nom_commune,
    population,
    nb_arrets_actuels,
    ROUND(arrets_pour_10000_hab::numeric, 2) as arrets_par_10k,
    CASE
        WHEN arrets_pour_10000_hab < 5 THEN 'Très mal desservie'
        WHEN arrets_pour_10000_hab < 10 THEN 'Mal desservie'
        WHEN arrets_pour_10000_hab < 20 THEN 'Moyennement desservie'
        ELSE 'Bien desservie'
    END as categorie_desserte
FROM mart.accessibilite_par_commune
ORDER BY arrets_pour_10000_hab ASC;

-- Q2: Inégalité par tranche de revenu (pauvres vs riches)
SELECT
    CASE
        WHEN revenu_median < 22000 THEN 'Q1 (plus pauvre)'
        WHEN revenu_median < 27000 THEN 'Q2'
        WHEN revenu_median < 33000 THEN 'Q3'
        ELSE 'Q4 (plus riche)'
    END as quartile_revenu,
    COUNT(*) as nb_communes,
    ROUND(AVG(arrets_pour_10000_hab)::numeric, 2) as avg_arrets_par_10k,
    ROUND(AVG(population)::numeric, 0) as avg_population,
    MIN(arrets_pour_10000_hab) as min_arrets_par_10k,
    MAX(arrets_pour_10000_hab) as max_arrets_par_10k
FROM mart.accessibilite_par_commune
GROUP BY quartile_revenu
ORDER BY quartile_revenu;

-- Q3: Communes pauvres ET mal desservies (cible du GPE ?)
SELECT
    code_commune,
    nom_commune,
    population,
    revenu_median,
    nb_arrets_actuels,
    ROUND(arrets_pour_10000_hab::numeric, 2) as arrets_par_10k,
    'Pauvre + Mal desservie' as situation
FROM mart.accessibilite_par_commune
WHERE revenu_median < 22000  -- Q1
  AND arrets_pour_10000_hab < 10
ORDER BY revenu_median ASC, arrets_pour_10000_hab ASC;
