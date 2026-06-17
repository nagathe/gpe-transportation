# tests/unit/test_fetch_insee.py
"""
Tests unitaires pour ingestion/fetch_insee.py
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from ingestion.fetch_insee import COLONNES_INSEE, download_insee, parse_insee


def make_zip_file(df: pd.DataFrame) -> Path:
    """Crée un ZIP temporaire sur disque, retourne le Path."""
    import zipfile

    csv_bytes = make_csv_bytes(df)
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp.name, "w") as zf:
        zf.writestr("dossier_complet.csv", csv_bytes)
    return Path(tmp.name)


def make_csv_bytes(df: pd.DataFrame) -> bytes:
    """Crée un CSV en bytes encodé latin-1 avec séparateur ;"""
    csv_str: str = df.to_csv(sep=";", index=False)
    return csv_str.encode("latin-1")


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
    """Crée un DataFrame INSEE minimal avec les colonnes attendues."""
    return pd.DataFrame(
        {
            "CODGEO": codgeo_list,
            "P22_POP": ["10000"] * len(codgeo_list),
            "MED_SL23": ["25000"] * len(codgeo_list),
            "P22_CHOM1564": ["500"] * len(codgeo_list),
            "P22_ACT1564": ["3000"] * len(codgeo_list),
            "C22_PMEN": ["4000"] * len(codgeo_list),
        }
    )


# --- download_insee ---


def test_download_insee_retourne_bytes() -> None:
    mock_response = MagicMock()
    mock_response.content = b"fake zip"
    mock_response.raise_for_status = MagicMock()

    with (
        patch(
            "ingestion.fetch_insee.requests.get",
            return_value=mock_response,
        ),
        patch("pathlib.Path.write_bytes"),
    ):
        result = download_insee("http://fake-url.fr")

    assert isinstance(result, Path)  # retourne un Path, pas des bytes
    assert result.suffix == ".zip"


def test_download_insee_leve_erreur_si_http_400() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("403")

    with patch(
        "ingestion.fetch_insee.requests.get",
        return_value=mock_response,
    ):
        with pytest.raises(requests.HTTPError):
            download_insee("http://fake-url.fr")


# --- parse_insee ---


def test_parse_insee_filtre_idf() -> None:
    """Seules les communes IDF doivent être retenues."""
    df = make_df_insee(["75056", "69123", "92012", "13055"])
    result = parse_insee(make_zip_file(df))
    assert set(result["code_commune"]) == {"75056", "92012"}


def test_parse_insee_retourne_dataframe() -> None:
    df = make_df_insee(["93001"])
    result = parse_insee(make_zip_file(df))
    assert isinstance(result, pd.DataFrame)


def test_parse_insee_colonnes_utiles_presentes() -> None:
    df = make_df_insee(["78646"])
    result = parse_insee(make_zip_file(df))
    for col in COLONNES_INSEE.values():
        assert col in result.columns


def test_parse_insee_leve_erreur_si_colonne_manquante() -> None:
    """Si une colonne attendue est absente du fichier source, on lève une KeyError."""
    df = make_df_insee(["91228"]).drop(columns=["MED_SL23"])
    with pytest.raises(KeyError):
        parse_insee(make_zip_file(df))


def test_parse_insee_colonne_dep_absente_du_resultat() -> None:
    """La colonne DEP ne doit pas apparaître en sortie."""
    df = make_df_insee(["94028"])
    result = parse_insee(make_zip_file(df))
    assert "DEP" not in result.columns
