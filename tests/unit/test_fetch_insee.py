# tests/unit/test_fetch_insee.py
"""
Tests unitaires pour ingestion/fetch_insee.py

Le fichier INSEE est au format Parquet « long » : une ligne = une mesure d'un
territoire pour une année. Les tests fabriquent un minuscule Parquet d'exemple.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from ingestion.fetch_insee import (
    COLONNES_SORTIE,
    MESURES_INSEE,
    download_insee,
    enrich_with_geo,
    fetch_commune_names,
    parse_insee,
)

# --- Fabrication d'un fichier Parquet d'exemple ---


def make_df_insee(
    codes: list[str],
    geo_object: str = "COM",
    annee: str = "2023",
    geo_ref: str = "2026",
    valeurs: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Une ligne par (commune, mesure retenue) au format long INSEE."""
    defaut = {
        "population": 10000.0,
        "revenu_median": 25000.0,
        "nb_chomeurs": 500.0,
        "nb_actifs": 3000.0,
        "nb_menages": 4000.0,
    }
    valeurs = {**defaut, **(valeurs or {})}
    rows = []
    for code in codes:
        for (id_tab, mesure), colonne in MESURES_INSEE.items():
            rows.append(
                {
                    "GEO_REF": geo_ref,
                    "GEO_OBJECT": geo_object,
                    "GEO": code,
                    "TIME_PERIOD": annee,
                    "ID_TAB": id_tab,
                    "TAB_MEASURE": mesure,
                    "OBS_VALUE": valeurs[colonne],
                    "UNIT_MULT": None,
                }
            )
    return pd.DataFrame(rows)


def write_parquet(df: pd.DataFrame, tmp_path: Path) -> Path:
    path = tmp_path / "dossier_complet.parquet"
    df.to_parquet(path, index=False)
    return path


def mock_http_response(chunks: list[bytes]) -> MagicMock:
    """Réponse HTTP simulée, utilisable comme gestionnaire de contexte."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.iter_content.return_value = iter(chunks)
    response.__enter__.return_value = response
    return response


# --- download_insee ---


def test_download_insee_ecrit_le_fichier_par_morceaux(tmp_path: Path) -> None:
    dest = tmp_path / "insee" / "dossier_complet.parquet"
    response = mock_http_response([b"abc", b"def"])

    with patch("ingestion.fetch_insee.requests.get", return_value=response):
        result = download_insee("http://fake-url.fr", dest)

    assert result == dest
    assert dest.read_bytes() == b"abcdef"
    assert not dest.with_suffix(".parquet.part").exists()  # pas de fichier temporaire


def test_download_insee_reutilise_le_fichier_existant(tmp_path: Path) -> None:
    dest = tmp_path / "dossier_complet.parquet"
    dest.write_bytes(b"deja la")

    with patch("ingestion.fetch_insee.requests.get") as mock_get:
        result = download_insee("http://fake-url.fr", dest)

    mock_get.assert_not_called()  # une panne du site n'empêche pas de relancer
    assert result == dest
    assert dest.read_bytes() == b"deja la"


def test_download_insee_leve_erreur_http_et_nettoie(tmp_path: Path) -> None:
    dest = tmp_path / "dossier_complet.parquet"
    response = mock_http_response([])
    response.raise_for_status.side_effect = requests.HTTPError("500")

    with patch("ingestion.fetch_insee.requests.get", return_value=response):
        with pytest.raises(requests.HTTPError):
            download_insee("http://fake-url.fr", dest)

    assert not dest.exists()
    assert not list(tmp_path.glob("*.part"))


def test_download_insee_leve_erreur_reseau_et_nettoie(tmp_path: Path) -> None:
    dest = tmp_path / "dossier_complet.parquet"

    with patch(
        "ingestion.fetch_insee.requests.get",
        side_effect=requests.ConnectionError("réseau"),
    ):
        with pytest.raises(requests.ConnectionError):
            download_insee("http://fake-url.fr", dest)

    assert not dest.exists()


# --- parse_insee ---


def test_parse_insee_filtre_idf(tmp_path: Path) -> None:
    """Seules les communes IDF doivent être retenues."""
    df = make_df_insee(["75056", "69123", "92012", "13055"])
    result = parse_insee(write_parquet(df, tmp_path))
    assert set(result["code_commune"]) == {"75056", "92012"}


def test_parse_insee_une_ligne_par_commune_et_bonnes_colonnes(tmp_path: Path) -> None:
    df = make_df_insee(["93001", "78646"])
    result = parse_insee(write_parquet(df, tmp_path))
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    for col in COLONNES_SORTIE + ["code_commune", "taux_chomage"]:
        assert col in result.columns
    ligne = result[result["code_commune"] == "93001"].iloc[0]
    assert ligne["population"] == 10000
    assert ligne["revenu_median"] == 25000


def test_parse_insee_garde_les_arrondissements(tmp_path: Path) -> None:
    arr = make_df_insee(["75101"], geo_object="ARM")
    result = parse_insee(write_parquet(arr, tmp_path))
    assert list(result["code_commune"]) == ["75101"]


def test_parse_insee_retire_paris_si_ses_arrondissements_sont_presents(
    tmp_path: Path,
) -> None:
    """Paris (75056) et ses arrondissements décrivent les mêmes habitants :
    on garde les arrondissements pour ne pas les compter deux fois."""
    df = pd.concat(
        [
            make_df_insee(["75056", "92012"]),
            make_df_insee(["75101", "75102"], geo_object="ARM"),
        ]
    )
    result = parse_insee(write_parquet(df, tmp_path))
    assert set(result["code_commune"]) == {"75101", "75102", "92012"}


def test_parse_insee_garde_paris_si_aucun_arrondissement(tmp_path: Path) -> None:
    """Sans arrondissements dans le fichier, on ne perd pas Paris."""
    df = make_df_insee(["75056", "92012"])
    result = parse_insee(write_parquet(df, tmp_path))
    assert set(result["code_commune"]) == {"75056", "92012"}


def test_parse_insee_ignore_les_autres_niveaux_geographiques(tmp_path: Path) -> None:
    """Un département ou un EPCI d'IDF ne doit pas être pris pour une commune."""
    df = pd.concat(
        [
            make_df_insee(["92012"]),
            make_df_insee(["92"], geo_object="DEP"),
            make_df_insee(["200054781"], geo_object="EPCI"),
        ]
    )
    result = parse_insee(write_parquet(df, tmp_path))
    assert list(result["code_commune"]) == ["92012"]


def test_parse_insee_garde_le_dernier_millesime(tmp_path: Path) -> None:
    df = pd.concat(
        [
            make_df_insee(["92012"], annee="2017", valeurs={"population": 1.0}),
            make_df_insee(["92012"], annee="2023", valeurs={"population": 2.0}),
        ]
    )
    result = parse_insee(write_parquet(df, tmp_path))
    assert len(result) == 1
    assert result.iloc[0]["population"] == 2.0


def test_parse_insee_deduplique_selon_le_millesime_geographique(
    tmp_path: Path,
) -> None:
    df = pd.concat(
        [
            make_df_insee(["92012"], geo_ref="2025", valeurs={"population": 1.0}),
            make_df_insee(["92012"], geo_ref="2026", valeurs={"population": 2.0}),
        ]
    )
    result = parse_insee(write_parquet(df, tmp_path))
    assert len(result) == 1
    assert result.iloc[0]["population"] == 2.0


def test_parse_insee_calcule_le_taux_de_chomage(tmp_path: Path) -> None:
    df = make_df_insee(["92012"], valeurs={"nb_chomeurs": 300.0, "nb_actifs": 3000.0})
    result = parse_insee(write_parquet(df, tmp_path))
    assert result.iloc[0]["taux_chomage"] == pytest.approx(0.1)


def test_parse_insee_taux_chomage_nan_si_actifs_nuls(tmp_path: Path) -> None:
    df = make_df_insee(["92012"], valeurs={"nb_actifs": 0.0})
    result = parse_insee(write_parquet(df, tmp_path))
    assert pd.isna(result.iloc[0]["taux_chomage"])


def test_parse_insee_applique_unit_mult(tmp_path: Path) -> None:
    df = make_df_insee(["92012"])
    df.loc[df["TAB_MEASURE"] == "POP", "UNIT_MULT"] = 3  # x 10^3
    result = parse_insee(write_parquet(df, tmp_path))
    assert result.iloc[0]["population"] == 10000 * 1000


def test_parse_insee_leve_erreur_si_mesure_manquante(tmp_path: Path) -> None:
    """Si une mesure attendue est absente du fichier, on lève une KeyError."""
    df = make_df_insee(["91228"])
    df = df[df["TAB_MEASURE"] != "MED_SL"]
    with pytest.raises(KeyError, match="revenu_median"):
        parse_insee(write_parquet(df, tmp_path))


def test_parse_insee_leve_erreur_si_colonne_absente(tmp_path: Path) -> None:
    """Si l'INSEE change la structure du fichier, on le signale clairement."""
    df: Any = make_df_insee(["91228"]).drop(columns=["TAB_MEASURE"])
    with pytest.raises(KeyError, match="TAB_MEASURE"):
        parse_insee(write_parquet(df, tmp_path))


# --- GeoAPI : coordonnées et noms, y compris les arrondissements de Paris ---


def make_geo_api(centres: bool = True) -> Any:
    """Simule GeoAPI : Paris (75056) par département, ses arrondissements à part."""

    def fake_get(url: str, timeout: int = 60) -> MagicMock:
        response = MagicMock()
        response.raise_for_status = MagicMock()
        if "arrondissement-municipal" in url:
            data: list[dict[str, Any]] = [
                {
                    "code": "75101",
                    "nom": "Paris 1er Arrondissement",
                    "centre": {"type": "Point", "coordinates": [2.3359, 48.862]},
                },
                {
                    "code": "75102",
                    "nom": "Paris 2e Arrondissement",
                    "centre": {"type": "Point", "coordinates": [2.3429, 48.8683]},
                },
            ]
        elif "/departements/75/" in url:
            data = [
                {
                    "code": "75056",
                    "nom": "Paris",
                    "centre": {"type": "Point", "coordinates": [2.347, 48.8589]},
                }
            ]
        else:
            data = []
        response.json.return_value = data
        return response

    return fake_get


def test_enrich_with_geo_donne_des_coordonnees_aux_arrondissements() -> None:
    df = pd.DataFrame({"code_commune": ["75101", "75102"]})
    with patch("ingestion.fetch_insee.requests.get", side_effect=make_geo_api()):
        result = enrich_with_geo(df)
    assert result["latitude"].notna().all()
    assert result["longitude"].notna().all()
    premier = result[result["code_commune"] == "75101"].iloc[0]
    assert premier["longitude"] == pytest.approx(2.3359)
    assert premier["latitude"] == pytest.approx(48.862)


def test_fetch_commune_names_prend_les_noms_des_arrondissements_dans_l_api() -> None:
    with (
        patch("ingestion.fetch_insee.requests.get", side_effect=make_geo_api()),
        patch("ingestion.fetch_insee.load_to_postgres") as mock_load,
    ):
        fetch_commune_names(MagicMock())
    noms = mock_load.call_args.args[0]
    arr = noms[noms["code_commune"] == "75102"]
    assert list(arr["nom_commune"]) == ["Paris 2e Arrondissement"]  # une seule fois
