-- ============================================
-- AUDIT DONNÉES GPE
-- ============================================

-- Nb gares total + par ligne
SELECT ligne_gpe, COUNT(*) as nb_gares
FROM raw.gpe_gares
GROUP BY ligne_gpe
ORDER BY ligne_gpe;

-- Gares sans géométrie
SELECT COUNT(*) as gares_sans_geom
FROM raw.gpe_gares
WHERE geometry IS NULL;

-- Vérif coordonnées cohérentes (IDF = lat 48-49, lon 1.5-3.5)
SELECT nom_gare, ligne_gpe,
  ST_X(geometry) as lon,
  ST_Y(geometry) as lat
FROM raw.gpe_gares
WHERE ST_X(geometry) NOT BETWEEN 1.5 AND 3.5
   OR ST_Y(geometry) NOT BETWEEN 48.0 AND 49.5;

-- ============================================
-- AUDIT DONNÉES INSEE
-- ============================================

-- Aperçu général
SELECT COUNT(*) as nb_communes,
  COUNT(revenu_median) as avec_revenu,
  COUNT(taux_chomage) as avec_chomage,
  COUNT(population) as avec_population
FROM raw.insee_communes;

-- Valeurs nulles
SELECT
  SUM(CASE WHEN revenu_median IS NULL THEN 1 ELSE 0 END) as revenu_null,
  SUM(CASE WHEN taux_chomage IS NULL THEN 1 ELSE 0 END) as chomage_null,
  SUM(CASE WHEN population IS NULL THEN 1 ELSE 0 END) as pop_null
FROM raw.insee_communes;

-- Valeurs aberrantes revenus
SELECT code_commune, revenu_median
FROM raw.insee_communes
WHERE revenu_median < 5000 OR revenu_median > 100000;

-- ============================================
-- AUDIT DONNÉES GTFS
-- ============================================

-- Nb arrêts total
SELECT COUNT(*) as nb_stops FROM raw.gtfs_stops;

-- Arrêts hors IDF
SELECT stop_id, stop_name, stop_lon, stop_lat
FROM raw.gtfs_stops
WHERE stop_lon::numeric NOT BETWEEN 1.5 AND 3.5
   OR stop_lat::numeric NOT BETWEEN 48.0 AND 49.5;

-- Doublons sur stop_id
SELECT stop_id, COUNT(*) 
FROM raw.gtfs_stops
GROUP BY stop_id
HAVING COUNT(*) > 1;

-- ============================================
-- COHÉRENCE CROISÉE
-- ============================================

-- Communes INSEE sans arrêt GTFS proche (> 5km)
-- (utile après le mart accessibilite)

-- Nb communes IDF dans INSEE vs attendu (~1300)
SELECT COUNT(*) as nb_communes FROM raw.insee_communes;

-- ============================================
-- STRUCTURE DE LA BASE
-- ============================================

-- Toutes les tables par schéma
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('raw', 'staging', 'mart')
ORDER BY table_schema, table_name;

-- ============================================
-- VOLUMÉTRIE PAR COUCHE
-- ============================================

-- Nombre de lignes par table (raw → staging → mart)
SELECT 'raw.insee_communes'              AS table_name, COUNT(*) FROM raw.insee_communes             UNION ALL
SELECT 'raw.gpe_gares',                                 COUNT(*) FROM raw.gpe_gares                  UNION ALL
SELECT 'raw.gtfs_stops',                                COUNT(*) FROM raw.gtfs_stops                 UNION ALL
SELECT 'raw.commune_names',                             COUNT(*) FROM raw.commune_names              UNION ALL
SELECT 'staging.stg_insee_communes',                    COUNT(*) FROM staging.stg_insee_communes     UNION ALL
SELECT 'staging.stg_gpe_gares',                         COUNT(*) FROM staging.stg_gpe_gares          UNION ALL
SELECT 'staging.stg_gtfs_stops',                        COUNT(*) FROM staging.stg_gtfs_stops         UNION ALL
SELECT 'mart.accessibilite_par_commune',                COUNT(*) FROM mart.accessibilite_par_commune UNION ALL
SELECT 'mart.gain_mobilite',                            COUNT(*) FROM mart.gain_mobilite             UNION ALL
SELECT 'mart.precarite_vs_mobilite',                    COUNT(*) FROM mart.precarite_vs_mobilite
ORDER BY table_name;

-- ============================================
-- COHÉRENCE INTER-COUCHES
-- ============================================

-- Communes sans nom après jointure commune_names
SELECT COUNT(*) AS communes_sans_nom
FROM mart.accessibilite_par_commune
WHERE nom_commune IS NULL;

-- ============================================
-- LOGIQUE MÉTIER
-- ============================================

-- Distribution des catégories de gain
SELECT categorie_gain,
       COUNT(*) AS nb_communes,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
FROM mart.gain_mobilite
GROUP BY categorie_gain
ORDER BY COUNT(*) DESC;

-- Distribution des profils de territoire
SELECT profil_territoire,
       COUNT(*) AS nb_communes,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
FROM mart.precarite_vs_mobilite
GROUP BY profil_territoire
ORDER BY COUNT(*) DESC;

-- Le GPE cible-t-il les zones précaires ? (question centrale)
SELECT quartile_revenu,
       COUNT(*) AS nb_communes,
       SUM(nb_gares_gpe_futures) AS total_gares_gpe
FROM mart.precarite_vs_mobilite
GROUP BY quartile_revenu
ORDER BY quartile_revenu;
