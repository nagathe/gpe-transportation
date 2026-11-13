# tests/unit/test_fetch_gtfs.py
"""
Tests unitaires pour ingestion/fetch_gtfs.py
"""

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from ingestion.fetch_gtfs import (
    STOPS_COLUMNS,
    download_gtfs,
    extract_gtfs,
    load_to_postgres,
    prepare_stops,
)


def make_zip(files: dict[str, str], path: Path) -> Path:
    """Crée un ZIP sur disque à partir d'un dict {nom_fichier: contenu_csv}."""
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return path


# --- download_gtfs ---


def test_download_gtfs_retourne_path(tmp_path: Path) -> None:
    mock_response = MagicMock()
    mock_response.content = b"fake zip content"
    mock_response.raise_for_status = MagicMock()

    with patch("ingestion.fetch_gtfs.requests.get", return_value=mock_response):
        result = download_gtfs("http://fake-url.fr", tmp_path)

    assert isinstance(result, Path)
    assert result.exists()


def test_download_gtfs_sauvegarde_contenu(tmp_path: Path) -> None:
    mock_response = MagicMock()
    mock_response.content = b"fake zip content"
    mock_response.raise_for_status = MagicMock()

    with patch("ingestion.fetch_gtfs.requests.get", return_value=mock_response):
        result = download_gtfs("http://fake-url.fr", tmp_path)

    assert result.read_bytes() == b"fake zip content"


def test_download_gtfs_leve_erreur_si_http_400(tmp_path: Path) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")

    with patch("ingestion.fetch_gtfs.requests.get", return_value=mock_response):
        with pytest.raises(requests.HTTPError):
            download_gtfs("http://fake-url.fr", tmp_path)


# --- extract_gtfs ---


def test_extract_gtfs_extrait_stops(tmp_path: Path) -> None:
    csv_content = "stop_id,stop_name,stop_lat,stop_lon\n1,Châtelet,48.86,2.35\n"
    zip_path = make_zip({"stops.txt": csv_content}, tmp_path / "test.zip")

    extract_gtfs(zip_path, tmp_path)

    assert (tmp_path / "stops.txt").exists()


def test_extract_gtfs_fichier_absent_ignore(tmp_path: Path) -> None:
    """Un fichier manquant dans le ZIP ne doit pas lever d'erreur."""
    zip_path = make_zip({"agency.txt": "agency_id\n1\n"}, tmp_path / "a.zip")

    # Ne doit pas lever d'erreur même si stops.txt est absent
    extract_gtfs(zip_path, tmp_path)

    assert not (tmp_path / "stops.txt").exists()


def test_extract_gtfs_n_extrait_que_stops(tmp_path: Path) -> None:
    """Seul stops.txt est extrait : routes, trips, stop_times ignorés."""
    zip_path = make_zip(
        {
            "stops.txt": "stop_id,stop_name\n1,Test\n",
            "routes.txt": "route_id\nR1\n",
            "trips.txt": "trip_id\nT1\n",
            "stop_times.txt": "trip_id,stop_id\nT1,1\n",
        },
        tmp_path / "test.zip",
    )

    extract_gtfs(zip_path, tmp_path)

    extraits = {p.name for p in tmp_path.glob("*.txt")}
    assert extraits == {"stops.txt"}


def test_extract_gtfs_zip_invalide_leve_erreur(tmp_path: Path) -> None:
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(b"ceci n'est pas un zip")

    with pytest.raises(zipfile.BadZipFile):
        extract_gtfs(bad_zip, tmp_path)


# --- load_to_postgres ---


def test_load_to_postgres_appelle_to_sql(tmp_path: Path) -> None:
    """load_to_postgres appelle to_sql quand stops.txt est présent."""
    csv_content = "stop_id,stop_name,stop_lat,stop_lon\n0001,Test,48.85,2.35\n"
    (tmp_path / "stops.txt").write_text(csv_content)

    mock_engine = MagicMock()

    with patch("pandas.DataFrame.to_sql") as mock_to_sql:
        load_to_postgres(tmp_path, mock_engine)
        assert mock_to_sql.called


def test_load_to_postgres_ids_gardes_en_string(tmp_path: Path) -> None:
    """Les IDs GTFS doivent rester en string (ex: '0001' ne devient pas 1)."""
    csv_content = "stop_id,stop_name\n0001,Test\n"
    (tmp_path / "stops.txt").write_text(csv_content)

    dataframes_charges = []

    def capture_to_sql(self: pd.DataFrame, *args, **kwargs) -> None:  # type: ignore
        dataframes_charges.append(self.copy())

    with patch.object(pd.DataFrame, "to_sql", capture_to_sql):
        load_to_postgres(tmp_path, MagicMock())

    assert dataframes_charges[0]["stop_id"].iloc[0] == "0001"


def test_load_to_postgres_leve_erreur_si_stops_absent(tmp_path: Path) -> None:
    """Sans stops.txt, l'ingestion échoue au lieu de ne rien charger."""
    with pytest.raises(FileNotFoundError):
        load_to_postgres(tmp_path, MagicMock())


def test_load_to_postgres_leve_erreur_si_table_absente(tmp_path: Path) -> None:
    """Si raw.gtfs_stops n'existe pas, on ne laisse pas pandas la créer."""
    (tmp_path / "stops.txt").write_text("stop_id\n1\n")
    mock_engine = MagicMock()
    mock_engine.dialect.has_table.return_value = False

    with patch("pandas.DataFrame.to_sql") as mock_to_sql:
        with pytest.raises(RuntimeError, match="make db-init"):
            load_to_postgres(tmp_path, mock_engine)

    assert not mock_to_sql.called


def test_load_to_postgres_vide_la_table_sans_la_supprimer(
    tmp_path: Path,
) -> None:
    """TRUNCATE puis ajout : ni DROP, ni référence au schéma staging."""
    (tmp_path / "stops.txt").write_text("stop_id\n1\n")
    mock_engine = MagicMock()
    mock_conn = mock_engine.begin.return_value.__enter__.return_value

    with patch("pandas.DataFrame.to_sql") as mock_to_sql:
        load_to_postgres(tmp_path, mock_engine)

    requetes = [str(c.args[0]) for c in mock_conn.execute.call_args_list]
    assert requetes == ["TRUNCATE TABLE raw.gtfs_stops"]
    assert mock_to_sql.call_args.kwargs["if_exists"] == "append"
    # Même connexion que le TRUNCATE, donc même transaction (#19)
    assert mock_to_sql.call_args.kwargs["con"] is mock_conn


# --- prepare_stops ---


def test_prepare_stops_garde_les_colonnes_du_ddl(tmp_path: Path) -> None:
    """Les colonnes hors DDL (zone_id, stop_access...) sont écartées."""
    entete = (
        "stop_id,stop_code,stop_name,stop_desc,stop_lon,stop_lat,zone_id,"
        "stop_url,location_type,parent_station,stop_timezone,level_id,"
        "wheelchair_boarding,platform_code,stop_access"
    )
    ligne = "IDFM:1,,Denfert,,2.33,48.83,1,,0,IDFM:71056,,,1,,"
    filepath = tmp_path / "stops.txt"
    filepath.write_text(f"{entete}\n{ligne}\n")

    df = prepare_stops(filepath)

    assert list(df.columns) == STOPS_COLUMNS


def test_prepare_stops_ajoute_les_colonnes_absentes(tmp_path: Path) -> None:
    """Une colonne facultative absente du fichier est ajoutée vide."""
    filepath = tmp_path / "stops.txt"
    filepath.write_text("stop_id,stop_name\n1,Test\n")

    df = prepare_stops(filepath)

    assert list(df.columns) == STOPS_COLUMNS
    assert df["stop_code"].isna().all()


def test_prepare_stops_convertit_les_types(tmp_path: Path) -> None:
    """Coordonnées en nombres, codes en entiers, identifiants en texte."""
    filepath = tmp_path / "stops.txt"
    filepath.write_text(
        "stop_id,stop_lat,stop_lon,location_type,wheelchair_boarding\n"
        "0001,48.83318643678081,2.333220634641387,1,\n"
    )

    df = prepare_stops(filepath)

    assert df["stop_id"].iloc[0] == "0001"
    assert df["stop_lat"].iloc[0] == pytest.approx(48.83318643678081)
    assert df["stop_lon"].iloc[0] == pytest.approx(2.333220634641387)
    assert df["location_type"].iloc[0] == 1
    assert str(df["location_type"].dtype) == "Int64"
    assert pd.isna(df["wheelchair_boarding"].iloc[0])


def test_prepare_stops_leve_erreur_sans_stop_id(tmp_path: Path) -> None:
    """Sans stop_id (clé primaire), le fichier est inutilisable."""
    filepath = tmp_path / "stops.txt"
    filepath.write_text("stop_name\nTest\n")

    with pytest.raises(ValueError, match="stop_id"):
        prepare_stops(filepath)
