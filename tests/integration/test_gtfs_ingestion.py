"""
Tests d'intégration pour l'ingestion GTFS.

Appelle le vrai fetch_gtfs.load_to_postgres sur une base temporaire
dont la structure vient de db/init.sql (fixture test_engine, conftest.py).
"""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from ingestion.fetch_gtfs import STOPS_COLUMNS, load_to_postgres

# En-tête réel du stops.txt d'IDFM (15 colonnes, dont 5 hors DDL)
ENTETE = (
    "stop_id,stop_code,stop_name,stop_desc,stop_lon,stop_lat,zone_id,"
    "stop_url,location_type,parent_station,stop_timezone,level_id,"
    "wheelchair_boarding,platform_code,stop_access"
)


def ecrire_stops(dossier: Path, lignes: list[str]) -> None:
    """Écrit un stops.txt (en-tête IDFM + lignes) dans le dossier."""
    contenu = "\n".join([ENTETE, *lignes]) + "\n"
    (dossier / "stops.txt").write_text(contenu)


@pytest.fixture
def stops_charges(test_engine: Engine, tmp_path: Path) -> Engine:
    """Charge 2 arrêts via load_to_postgres et retourne l'engine."""
    ecrire_stops(
        tmp_path,
        [
            "0001,,Denfert-Rochereau,,2.333220634641387,48.83318643678081,"
            "1,,0,IDFM:71056,,,1,,",
            "IDFM:2,,Cité Universitaire,,2.3388576809777035,"
            "48.82150600684166,1,,0,IDFM:70623,,,2,,",
        ],
    )
    load_to_postgres(tmp_path, test_engine)
    return test_engine


def test_charge_toutes_les_lignes(stops_charges: Engine) -> None:
    """Les 2 arrêts du fichier sont en base."""
    with stops_charges.connect() as conn:
        requete = text("SELECT COUNT(*) FROM raw.gtfs_stops")
        assert conn.execute(requete).scalar() == 2


def test_colonnes_du_ddl_uniquement(stops_charges: Engine) -> None:
    """La table garde les 10 colonnes de init.sql (pas zone_id, etc.)."""
    with stops_charges.connect() as conn:
        colonnes = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'raw' AND table_name = 'gtfs_stops' "
                "ORDER BY ordinal_position"
            )
        ).scalars()
        assert list(colonnes) == STOPS_COLUMNS


def test_cle_primaire_conservee(stops_charges: Engine) -> None:
    """Après chargement, stop_id est toujours la clé primaire (#20)."""
    with stops_charges.connect() as conn:
        colonnes_pk = conn.execute(
            text(
                "SELECT kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                " AND tc.table_schema = kcu.table_schema "
                "WHERE tc.table_schema = 'raw' "
                "  AND tc.table_name = 'gtfs_stops' "
                "  AND tc.constraint_type = 'PRIMARY KEY'"
            )
        ).scalars()
        assert list(colonnes_pk) == ["stop_id"]


def test_identifiants_restent_du_texte(stops_charges: Engine) -> None:
    """'0001' ne devient pas 1."""
    with stops_charges.connect() as conn:
        ids = conn.execute(
            text("SELECT stop_id FROM raw.gtfs_stops ORDER BY stop_id")
        ).scalars()
        assert list(ids) == ["0001", "IDFM:2"]


def test_coordonnees_et_codes_types(stops_charges: Engine) -> None:
    """Coordonnées numériques (8 décimales du DDL), codes entiers."""
    with stops_charges.connect() as conn:
        lat, lon, location_type = conn.execute(
            text(
                "SELECT stop_lat, stop_lon, location_type "
                "FROM raw.gtfs_stops WHERE stop_id = '0001'"
            )
        ).one()
    assert float(lat) == pytest.approx(48.83318644)
    assert float(lon) == pytest.approx(2.33322063)
    assert location_type == 0


def test_rechargement_remplace_les_donnees(
    stops_charges: Engine, tmp_path: Path
) -> None:
    """Un second chargement remplace les données, sans accumulation."""
    nouveau_dossier = tmp_path / "second"
    nouveau_dossier.mkdir()
    ecrire_stops(nouveau_dossier, ["STOP_999,,Nouvelle Gare,,2.1,48.7,,,,,,,,,"])

    load_to_postgres(nouveau_dossier, stops_charges)

    with stops_charges.connect() as conn:
        ids = conn.execute(text("SELECT stop_id FROM raw.gtfs_stops"))
        assert list(ids.scalars()) == ["STOP_999"]


def test_vue_dependante_survit_au_rechargement(
    stops_charges: Engine, tmp_path: Path
) -> None:
    """Une vue sur raw.gtfs_stops reste valide après rechargement (#24)."""
    with stops_charges.begin() as conn:
        conn.execute(
            text(
                "CREATE VIEW staging.vue_test AS " "SELECT stop_id FROM raw.gtfs_stops"
            )
        )

    load_to_postgres(tmp_path, stops_charges)

    with stops_charges.connect() as conn:
        requete = text("SELECT COUNT(*) FROM staging.vue_test")
        assert conn.execute(requete).scalar() == 2


def test_fichier_sans_arret_vide_la_table(
    stops_charges: Engine, tmp_path: Path
) -> None:
    """Un stops.txt sans ligne charge zéro arrêt, sans erreur."""
    dossier_vide = tmp_path / "vide"
    dossier_vide.mkdir()
    ecrire_stops(dossier_vide, [])

    load_to_postgres(dossier_vide, stops_charges)

    with stops_charges.connect() as conn:
        requete = text("SELECT COUNT(*) FROM raw.gtfs_stops")
        assert conn.execute(requete).scalar() == 0
