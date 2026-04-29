# tests/unit/test_fetch_insee.py
"""
Tests unitaires pour ingestion/fetch_insee.py
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from ingestion.fetch_insee import COLONNES_UTILES, download_insee, parse_insee


def make_csv_bytes(df: pd.DataFrame) -> bytes:
    """Crée un CSV en bytes encodé latin-1 avec séparateur ;"""
    return df.to_csv(sep=";", index=False).encode("latin-1")


def make_zip_bytes(df: pd.DataFrame) -> bytes:
    """Crée un ZIP contenant dossier_complet.csv à partir d'un DataFrame."""
    import io
    import zipfile

    csv_bytes = make_csv_bytes(df)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("dossier_complet.csv", csv_bytes)
    return buffer.getvalue()


def make_df_insee(codgeo_list: list[str]) -> pd.DataFrame:
    """Crée un DataFrame INSEE minimal avec les colonnes attendues (année 21)."""
    return pd.DataFrame(
        {
            "CODGEO": codgeo_list,
            "MED21": ["25000"] * len(codgeo_list),
            "TP6021": ["15.2"] * len(codgeo_list),
            "NBPERSMENFISC21": ["5000"] * len(codgeo_list),
        }
    )


# --- download_insee ---


def test_download_insee_retourne_bytes() -> None:
    mock_response = MagicMock()
    mock_response.content = b"fake zip"
    mock_response.raise_for_status = MagicMock()

    with patch("ingestion.fetch_insee.requests.get", return_value=mock_response):
        result = download_insee("http://fake-url.fr")

    assert isinstance(result, bytes)


def test_download_insee_leve_erreur_si_http_400() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("403")

    with patch("ingestion.fetch_insee.requests.get", return_value=mock_response):
        with pytest.raises(requests.HTTPError):
            download_insee("http://fake-url.fr")


# --- parse_insee ---


def test_parse_insee_filtre_idf() -> None:
    """Seules les communes IDF doivent être retenues."""
    df = make_df_insee(["75056", "69123", "92012", "13055"])
    result = parse_insee(make_zip_bytes(df))
    assert set(result["CODGEO"]) == {"75056", "92012"}


def test_parse_insee_retourne_dataframe() -> None:
    df = make_df_insee(["93001"])
    result = parse_insee(make_zip_bytes(df))
    assert isinstance(result, pd.DataFrame)


def test_parse_insee_colonnes_utiles_presentes() -> None:
    df = make_df_insee(["78646"])
    result = parse_insee(make_zip_bytes(df))
    for col in COLONNES_UTILES:
        assert col in result.columns


def test_parse_insee_leve_erreur_si_colonne_manquante() -> None:
    """Si une colonne attendue est absente du fichier source, on lève une KeyError."""
    df = make_df_insee(["91228"]).drop(columns=["MED21"])
    result_bytes = make_zip_bytes(df)

    with pytest.raises(KeyError):
        parse_insee(result_bytes)


def test_parse_insee_colonne_dep_absente_du_resultat() -> None:
    """La colonne DEP ne doit pas apparaître en sortie."""
    df = make_df_insee(["94028"])
    result = parse_insee(make_zip_bytes(df))
    assert "DEP" not in result.columns
