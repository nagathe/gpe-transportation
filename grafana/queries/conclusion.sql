-- ============================================================================
-- Conclusion : Le GPE réduit-il les inégalités ?
-- ============================================================================
-- Synthèse des impacts du GPE sur les inégalités de mobilité

-- Q1: Vue synthétique - avant/après par quartile de revenu
WITH avant AS (
    SELECT
        CASE
            WHEN a.revenu_median < 22000 THEN 'Q1 (très pauvre)'
            WHEN a.revenu_median < 27000 THEN 'Q2'
            WHEN a.revenu_median < 33000 THEN 'Q3'
            ELSE 'Q4 (riche)'
        END as quartile,
        ROUND(AVG(a.arrets_pour_10000_hab)::numeric, 2) as avg_arrets_avant
    FROM mart.accessibilite_par_commune a
    GROUP BY quartile
),
apres AS (
    SELECT
        CASE
            WHEN a.revenu_median < 22000 THEN 'Q1 (très pauvre)'
            WHEN a.revenu_median < 27000 THEN 'Q2'
            WHEN a.revenu_median < 33000 THEN 'Q3'
            ELSE 'Q4 (riche)'
        END as quartile,
        COUNT(*) as nb_communes,
        SUM(CASE WHEN g.nb_gares_gpe_futures > 0 THEN 1 ELSE 0 END) as communes_gpe,
        ROUND(AVG(CASE WHEN g.categorie_gain = 'Fort gain' THEN 1 ELSE 0 END)::numeric * 100, 2) as pct_fort_gain
    FROM mart.gain_mobilite g
    JOIN mart.accessibilite_par_commune a USING (code_commune)
    GROUP BY quartile
)
SELECT
    av.quartile,
    av.avg_arrets_avant,
    ap.nb_communes,
    ap.communes_gpe,
    ap.pct_fort_gain
FROM avant av
JOIN apres ap ON av.quartile = ap.quartile
ORDER BY av.quartile;

-- Q2: % de communes pauvres aidées vs riches aidées
WITH pauvres AS (
    SELECT
        COUNT(*) as nb_pauvres,
        SUM(CASE WHEN g.nb_gares_gpe_futures > 0 THEN 1 ELSE 0 END) as pauvres_avec_gpe
    FROM mart.gain_mobilite g
    JOIN mart.accessibilite_par_commune a USING (code_commune)
    WHERE a.revenu_median < 22000
),
riches AS (
    SELECT
        COUNT(*) as nb_riches,
        SUM(CASE WHEN g.nb_gares_gpe_futures > 0 THEN 1 ELSE 0 END) as riches_avec_gpe
    FROM mart.gain_mobilite g
    JOIN mart.accessibilite_par_commune a USING (code_commune)
    WHERE a.revenu_median >= 33000
)
SELECT
    'Pauvres (Q1)' as groupe,
    p.nb_pauvres as nb_communes,
    p.pauvres_avec_gpe as communes_avec_gpe,
    ROUND(100.0 * p.pauvres_avec_gpe / p.nb_pauvres::numeric, 2) as pct_aidees
FROM pauvres p
UNION ALL
SELECT
    'Riches (Q4)' as groupe,
    r.nb_riches as nb_communes,
    r.riches_avec_gpe as communes_avec_gpe,
    ROUND(100.0 * r.riches_avec_gpe / r.nb_riches::numeric, 2) as pct_aidees
FROM riches r;

-- Q3: Bilan final - inégalité réduite ou aggravée ?
-- Comparaison : écart d'accessibilité avant/après
SELECT
    'INÉGALITÉ AVANT GPE' as periode,
    ROUND((
        SELECT MAX(arrets_pour_10000_hab) FROM mart.accessibilite_par_commune
        WHERE revenu_median >= 33000  -- riches
    ) - (
        SELECT AVG(arrets_pour_10000_hab) FROM mart.accessibilite_par_commune
        WHERE revenu_median < 22000  -- pauvres
    )::numeric, 2) as ecart_inegalite
UNION ALL
SELECT
    'INÉGALITÉ APRÈS GPE (simulée)',
    ROUND((
        SELECT MAX(arrets_pour_10000_hab) FROM mart.accessibilite_par_commune
        WHERE revenu_median >= 33000
    ) - (
        SELECT AVG(
            CASE
                WHEN g.nb_gares_gpe_futures > 0 THEN 1  -- simplif: +1 gare
                ELSE 0
            END
        ) FROM mart.gain_mobilite g
        JOIN mart.accessibilite_par_commune a USING (code_commune)
        WHERE a.revenu_median < 22000
    )::numeric, 2)
;
