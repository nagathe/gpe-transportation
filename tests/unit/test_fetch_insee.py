# tests/unit/test_fetch_insee.py

"""
Tests unitaires pour ingestion/fetch_insee.py
On teste parse_insee et download_insee sans appel réseau ni base.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from ingestion.fetch_insee import COLONNES_UTILES, download_insee, parse_insee


def make_csv_bytes(df: pd.DataFrame) -> bytes:
    """Crée un CSV en bytes encodé latin-1 avec séparateur ;"""
    return df.to_csv(sep=";", index=False).encode("latin-1")


def make_df_insee(codgeo_list: list[str]) -> pd.DataFrame:
    """Crée un DataFrame INSEE minimal avec les colonnes attendues."""
    return pd.DataFrame(
        {
            "CODGEO": codgeo_list,
            "LIBGEO": [f"Commune {c}" for c in codgeo_list],
            "MED20": ["25000"] * len(codgeo_list),
            "TP6020": ["15.2"] * len(codgeo_list),
            "NBPERSMENFISC20": ["5000"] * len(codgeo_list),
        }
    )


# --- download_insee ---


def test_download_insee_retourne_bytes():
    mock_response = MagicMock()
    mock_response.content = b"fake csv"
    mock_response.raise_for_status = MagicMock()

    with patch("ingestion.fetch_insee.requests.get", return_value=mock_response):
        result = download_insee("http://fake-url.fr")

    assert isinstance(result, bytes)


def test_download_insee_leve_erreur_si_http_400():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("403")

    with patch("ingestion.fetch_insee.requests.get", return_value=mock_response):
        with pytest.raises(requests.HTTPError):
            download_insee("http://fake-url.fr")


# --- parse_insee ---


def test_parse_insee_filtre_idf():
    """Seules les communes IDF doivent être retenues."""
    df = make_df_insee(
        ["75056", "69123", "92012", "13055"]
    )  # Paris, Lyon, Hauts-de-Seine, Marseille
    raw = make_csv_bytes(df)

    result = parse_insee(raw)

    assert set(result["CODGEO"]) == {"75056", "92012"}


def test_parse_insee_retourne_dataframe():
    df = make_df_insee(["93001"])
    result = parse_insee(make_csv_bytes(df))
    assert isinstance(result, pd.DataFrame)


def test_parse_insee_colonnes_utiles_presentes():
    df = make_df_insee(["78646"])
    result = parse_insee(make_csv_bytes(df))
    for col in COLONNES_UTILES:
        assert col in result.columns


def test_parse_insee_leve_erreur_si_colonne_manquante():
    """Si une colonne attendue est absente du fichier source, on lève une KeyError."""
    df = make_df_insee(["91228"]).drop(columns=["MED20"])
    raw = df.to_csv(sep=";", index=False).encode("latin-1")

    with pytest.raises(KeyError):
        parse_insee(raw)


def test_parse_insee_colonne_dep_absente_du_resultat():
    """La colonne DEP est un intermédiaire de calcul, elle ne doit pas apparaître en sortie."""
    df = make_df_insee(["94028"])
    result = parse_insee(make_csv_bytes(df))
    assert "DEP" not in result.columns
