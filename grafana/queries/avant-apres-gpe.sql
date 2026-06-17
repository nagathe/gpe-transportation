-- ============================================================================
-- Impact du GPE : Avant vs Après
-- ============================================================================
-- Analyse : Le GPE va-t-il réduire les inégalités ?
-- Qui gagne le plus ? Les pauvres sont-ils aidés ?

-- Q1: Gain d'accessibilité par commune (avant/après GPE)
SELECT
    g.code_commune,
    g.nom_commune,
    a.population,
    a.revenu_median,
    a.nb_arrets_actuels as arrets_avant,
    g.nb_gares_gpe_futures,
    CASE
        WHEN g.nb_gares_gpe_futures > 0 THEN 'Avec GPE'
        ELSE 'Sans GPE'
    END as situation_gpe,
    g.categorie_gain,
    ROUND(a.arrets_pour_10000_hab::numeric, 2) as arrets_par_10k_avant,
    CASE
        WHEN a.revenu_median < 22000 THEN 'Q1 (très pauvre)'
        WHEN a.revenu_median < 27000 THEN 'Q2'
        WHEN a.revenu_median < 33000 THEN 'Q3'
        ELSE 'Q4 (riche)'
    END as quartile_revenu
FROM mart.gain_mobilite g
JOIN mart.accessibilite_par_commune a USING (code_commune)
ORDER BY g.nb_gares_gpe_futures DESC, a.arrets_pour_10000_hab ASC;

-- Q2: Impact du GPE par quartile de revenu
-- Montre si le GPE aide plus les pauvres ou les riches
SELECT
    CASE
        WHEN a.revenu_median < 22000 THEN 'Q1 (très pauvre)'
        WHEN a.revenu_median < 27000 THEN 'Q2'
        WHEN a.revenu_median < 33000 THEN 'Q3'
        ELSE 'Q4 (riche)'
    END as quartile_revenu,
    COUNT(*) as nb_communes,
    SUM(CASE WHEN g.nb_gares_gpe_futures > 0 THEN 1 ELSE 0 END) as communes_avec_gpe,
    ROUND(100.0 * SUM(CASE WHEN g.nb_gares_gpe_futures > 0 THEN 1 ELSE 0 END) / COUNT(*)::numeric, 2) as pct_communes_avec_gpe,
    ROUND(AVG(g.nb_gares_gpe_futures)::numeric, 2) as avg_nb_gares_par_commune
FROM mart.gain_mobilite g
JOIN mart.accessibilite_par_commune a USING (code_commune)
GROUP BY quartile_revenu
ORDER BY quartile_revenu;

-- Q3: Top 20 communes avec le plus grand gain de mobilité
-- Qui gagne vraiment le plus ?
SELECT
    g.code_commune,
    g.nom_commune,
    a.population,
    a.revenu_median,
    CASE
        WHEN a.revenu_median < 22000 THEN 'Q1 (très pauvre)'
        WHEN a.revenu_median < 27000 THEN 'Q2'
        WHEN a.revenu_median < 33000 THEN 'Q3'
        ELSE 'Q4 (riche)'
    END as quartile_revenu,
    g.nb_gares_gpe_futures,
    g.categorie_gain,
    ROUND(a.arrets_pour_10000_hab::numeric, 2) as arrets_actuels_par_10k
FROM mart.gain_mobilite g
JOIN mart.accessibilite_par_commune a USING (code_commune)
WHERE g.nb_gares_gpe_futures > 0
ORDER BY g.nb_gares_gpe_futures DESC
LIMIT 20;

-- Q4: Communes pauvres + mal desservies : vont-elles être aidées ?
SELECT
    g.code_commune,
    g.nom_commune,
    a.population,
    a.revenu_median,
    a.nb_arrets_actuels,
    ROUND(a.arrets_pour_10000_hab::numeric, 2) as arrets_par_10k,
    g.nb_gares_gpe_futures,
    g.categorie_gain,
    CASE
        WHEN g.nb_gares_gpe_futures > 0 AND a.arrets_pour_10000_hab < 10 THEN 'OUI - Cible du GPE'
        WHEN g.nb_gares_gpe_futures = 0 AND a.arrets_pour_10000_hab < 10 THEN 'NON - Reste mal desservie'
        ELSE 'Autre'
    END as impact_gpe
FROM mart.gain_mobilite g
JOIN mart.accessibilite_par_commune a USING (code_commune)
WHERE a.revenu_median < 22000  -- Q1 pauvres
  AND a.arrets_pour_10000_hab < 10  -- mal desservies
ORDER BY g.nb_gares_gpe_futures DESC;
