# tests/unit/test_fetch_gpe.py
"""
Tests unitaires pour ingestion/fetch_gpe.py

On teste la logique pure (parsing shapefile, filtrage lignes GPE)
sans appel réseau ni base de données. Les dépendances externes sont mockées.
"""

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest
import requests
from shapely.geometry import Point

from ingestion.fetch_gpe import LIGNES_GPE, download_gpe, extract_gpe, parse_gpe

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def make_shapefile(tmp_path: Path, rows: list[dict]) -> Path:
    """Crée un shapefile minimal dans tmp_path à partir d'une liste de dicts.

    Chaque dict doit contenir : LIBELLE, LIGNE, CONNEX, producteur, geometry.
    Retourne le dossier contenant le .shp.
    """
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    gdf.to_file(shp_dir / "gpe.shp")
    return shp_dir


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def shp_valide(tmp_path: Path) -> Path:
    """Shapefile minimal avec 2 gares GPE valides (L15 et L16)."""
    return make_shapefile(
        tmp_path,
        [
            {
                "LIBELLE": "Saint-Denis Pleyel",
                "LIGNE": "L15",
                "CONNEX": "Oui",
                "producteur": "SDGP",
                "geometry": Point(2.3536, 48.9236),
            },
            {
                "LIBELLE": "Noisy-Champs",
                "LIGNE": "L16",
                "CONNEX": "Non",
                "producteur": "SDGP",
                "geometry": Point(2.6478, 48.8402),
            },
        ],
    )


@pytest.fixture
def shp_avec_hors_gpe(tmp_path: Path) -> Path:
    """Shapefile avec 1 gare GPE et 1 gare hors GPE — la hors GPE doit être filtrée."""
    return make_shapefile(
        tmp_path,
        [
            {
                "LIBELLE": "Champigny Centre",
                "LIGNE": "L15",
                "CONNEX": "Non",
                "producteur": "SDGP",
                "geometry": Point(2.5149, 48.8167),
            },
            {
                "LIBELLE": "Gare du Nord",
                "LIGNE": "RER_B",  # hors GPE
                "CONNEX": "Oui",
                "producteur": "SNCF",
                "geometry": Point(2.3553, 48.8809),
            },
        ],
    )


@pytest.fixture
def shp_vide(tmp_path: Path) -> Path:
    """Shapefile sans aucune gare GPE après filtrage."""
    return make_shapefile(
        tmp_path,
        [
            {
                "LIBELLE": "Gare du Nord",
                "LIGNE": "RER_B",
                "CONNEX": "Oui",
                "producteur": "SNCF",
                "geometry": Point(2.3553, 48.8809),
            }
        ],
    )


# ─────────────────────────────────────────────
# Tests parse_gpe
# ─────────────────────────────────────────────


class TestParseGpe:
    def test_retourne_geodataframe(self, shp_valide: Path) -> None:
        """parse_gpe doit retourner un GeoDataFrame."""
        result = parse_gpe(shp_valide)
        assert isinstance(result, gpd.GeoDataFrame)

    def test_nombre_lignes(self, shp_valide: Path) -> None:
        """On doit avoir autant de lignes que de gares GPE dans le shapefile."""
        result = parse_gpe(shp_valide)
        assert len(result) == 2

    def test_colonnes_presentes(self, shp_valide: Path) -> None:
        """Le GeoDataFrame doit contenir les colonnes métier attendues."""
        result = parse_gpe(shp_valide)
        colonnes_attendues = {
            "nom_gare",
            "ligne_gpe",
            "interconnexion",
            "source",
            "geometry",
        }
        assert colonnes_attendues.issubset(set(result.columns))

    def test_filtre_hors_gpe(self, shp_avec_hors_gpe: Path) -> None:
        """Les gares dont la ligne n'est pas dans LIGNES_GPE doivent être filtrées."""
        result = parse_gpe(shp_avec_hors_gpe)
        assert len(result) == 1
        assert result.iloc[0]["nom_gare"] == "Champigny Centre"

    def test_valeurs_nom_gare(self, shp_valide: Path) -> None:
        """Les noms de gares doivent correspondre aux données source."""
        result = parse_gpe(shp_valide)
        noms = result["nom_gare"].tolist()
        assert "Saint-Denis Pleyel" in noms
        assert "Noisy-Champs" in noms

    def test_crs_est_wgs84(self, shp_valide: Path) -> None:
        """Le GeoDataFrame doit être en WGS84 (EPSG:4326) après reprojection."""
        result = parse_gpe(shp_valide)
        assert result.crs.to_epsg() == 4326

    def test_shapefile_absent_leve_erreur(self, tmp_path: Path) -> None:
        """Un dossier sans .shp doit lever FileNotFoundError."""
        dossier_vide = tmp_path / "vide"
        dossier_vide.mkdir()
        with pytest.raises(FileNotFoundError, match="Aucun shapefile"):
            parse_gpe(dossier_vide)

    def test_toutes_lignes_hors_gpe_leve_erreur(self, shp_vide: Path) -> None:
        """Si aucune gare ne passe le filtre GPE, on doit avoir 0 lignes."""
        result = parse_gpe(shp_vide)
        assert len(result) == 0


# ─────────────────────────────────────────────
# Tests download_gpe
# ─────────────────────────────────────────────


class TestDownloadGpe:
    def test_retourne_path(self, tmp_path: Path) -> None:
        """download_gpe doit retourner un Path vers le ZIP sauvegardé."""
        mock_response = MagicMock()
        mock_response.content = b"fake zip"
        mock_response.raise_for_status.return_value = None

        with patch("ingestion.fetch_gpe.requests.get", return_value=mock_response):
            result = download_gpe("http://fake-url.com/gpe.zip", tmp_path)

        assert isinstance(result, Path)
        assert result.exists()

    def test_zip_sauvegarde_contenu(self, tmp_path: Path) -> None:
        """Le contenu du ZIP doit être correctement écrit sur disque."""
        mock_response = MagicMock()
        mock_response.content = b"fake zip content"
        mock_response.raise_for_status.return_value = None

        with patch("ingestion.fetch_gpe.requests.get", return_value=mock_response):
            result = download_gpe("http://fake-url.com/gpe.zip", tmp_path)

        assert result.read_bytes() == b"fake zip content"

    def test_zip_deja_present_pas_retelecharge(self, tmp_path: Path) -> None:
        """Si le ZIP existe déjà, il ne doit pas être retéléchargé."""
        zip_path = tmp_path / "gpe_gares.zip"
        zip_path.write_bytes(b"existing content")

        with patch("ingestion.fetch_gpe.requests.get") as mock_get:
            result = download_gpe("http://fake-url.com/gpe.zip", tmp_path)
            mock_get.assert_not_called()

        assert result.read_bytes() == b"existing content"

    def test_leve_erreur_si_http_400(self, tmp_path: Path) -> None:
        """download_gpe doit lever HTTPError si le serveur répond en erreur."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404")

        with patch("ingestion.fetch_gpe.requests.get", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                download_gpe("http://fake-url.com/gpe.zip", tmp_path)


# ─────────────────────────────────────────────
# Tests extract_gpe
# ─────────────────────────────────────────────


class TestExtractGpe:
    def test_retourne_path(self, tmp_path: Path) -> None:
        """extract_gpe doit retourner le chemin du dossier d'extraction."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("gpe.shp", b"fake shp")

        result = extract_gpe(zip_path)
        assert isinstance(result, Path)
        assert result.exists()

    def test_fichiers_extraits(self, tmp_path: Path) -> None:
        """Les fichiers du ZIP doivent être présents dans le dossier extrait."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("gpe.shp", b"fake shp")
            z.writestr("gpe.dbf", b"fake dbf")

        extract_dir = extract_gpe(zip_path)
        assert (extract_dir / "gpe.shp").exists()
        assert (extract_dir / "gpe.dbf").exists()
