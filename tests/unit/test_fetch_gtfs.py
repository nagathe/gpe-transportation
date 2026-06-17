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

from ingestion.fetch_gtfs import download_gtfs, extract_gtfs, load_to_postgres


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
    csv_content = "stop_id,stop_name\n1,Test\n"
    zip_path = make_zip({"stops.txt": csv_content}, tmp_path / "test.zip")

    # Ne doit pas lever d'erreur même si routes.txt est absent
    extract_gtfs(zip_path, tmp_path)

    assert (tmp_path / "stops.txt").exists()
    assert not (tmp_path / "routes.txt").exists()


def test_extract_gtfs_zip_invalide_leve_erreur(tmp_path: Path) -> None:
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(b"ceci n'est pas un zip")

    with pytest.raises(zipfile.BadZipFile):
        extract_gtfs(bad_zip, tmp_path)


# --- load_to_postgres ---


def test_load_to_postgres_appelle_to_sql(tmp_path: Path) -> None:
    """load_to_postgres appelle to_sql pour chaque fichier présent."""
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
