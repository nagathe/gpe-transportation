# tests/unit/test_fetch_gtfs.py

"""
Tests unitaires pour ingestion/fetch_gtfs.py
On teste extract_gtfs et download_gtfs sans appel réseau ni base.
"""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from ingestion.fetch_gtfs import download_gtfs, extract_gtfs


def make_zip(files: dict[str, str]) -> bytes:
    """Crée un zip en mémoire à partir d'un dict {nom_fichier: contenu_csv}."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buffer.getvalue()


# --- download_gtfs ---


def test_download_gtfs_retourne_bytes():
    mock_response = MagicMock()
    mock_response.content = b"fake zip content"
    mock_response.raise_for_status = MagicMock()

    with patch("ingestion.fetch_gtfs.requests.get", return_value=mock_response):
        result = download_gtfs("http://fake-url.fr")

    assert isinstance(result, bytes)
    assert result == b"fake zip content"


def test_download_gtfs_leve_erreur_si_http_400():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")

    with patch("ingestion.fetch_gtfs.requests.get", return_value=mock_response):
        with pytest.raises(requests.HTTPError):
            download_gtfs("http://fake-url.fr")


# --- extract_gtfs ---


def test_extract_gtfs_retourne_dataframe_stops():
    csv_content = "stop_id,stop_name,stop_lat,stop_lon\n1,Châtelet,48.86,2.35\n"
    zip_content = make_zip({"stops.txt": csv_content})

    result = extract_gtfs(zip_content)

    assert "stops" in result
    assert isinstance(result["stops"], pd.DataFrame)
    assert len(result["stops"]) == 1


def test_extract_gtfs_colonnes_presentes():
    csv_content = "stop_id,stop_name,stop_lat,stop_lon\n1,Nation,48.84,2.39\n"
    zip_content = make_zip({"stops.txt": csv_content})

    result = extract_gtfs(zip_content)

    assert "stop_id" in result["stops"].columns
    assert "stop_lat" in result["stops"].columns


def test_extract_gtfs_fichier_absent_ignore():
    """Un fichier manquant dans le zip ne doit pas lever d'erreur, juste être ignoré."""
    csv_content = "stop_id,stop_name\n1,Test\n"
    # On ne met que stops.txt, pas routes.txt etc.
    zip_content = make_zip({"stops.txt": csv_content})

    result = extract_gtfs(zip_content)

    assert "stops" in result
    assert "routes" not in result


def test_extract_gtfs_zip_invalide_leve_erreur():
    with pytest.raises(zipfile.BadZipFile):
        extract_gtfs(b"ceci n'est pas un zip")


def test_extract_gtfs_ids_gardes_en_string():
    """Les IDs GTFS doivent rester en
    string (ex: stop_id '0001' ne devient pas 1)."""
    csv_content = "stop_id,stop_name\n0001,Test\n"
    zip_content = make_zip({"stops.txt": csv_content})

    result = extract_gtfs(zip_content)

    assert result["stops"]["stop_id"].iloc[0] == "0001"
