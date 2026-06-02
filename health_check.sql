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
WHERE stop_lon NOT BETWEEN 1.5 AND 3.5
   OR stop_lat NOT BETWEEN 48.0 AND 49.5;

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
