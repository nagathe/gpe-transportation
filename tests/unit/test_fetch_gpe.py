# tests/unit/test_fetch_gpe.py

"""
Tests unitaires pour ingestion/fetch_gpe.py

On teste la logique pure (parsing, nettoyage) sans appel réseau ni base de données.
Les dépendances externes sont mockées.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ingestion.fetch_gpe import download_gpe, parse_gpe

# ─────────────────────────────────────────────
# Fixtures — données de test réutilisables
# ─────────────────────────────────────────────


@pytest.fixture
def geojson_valide() -> dict:
    """GeoJSON minimal valide avec 2 gares GPE."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "properties": {
                    "nom_gare": "Saint-Denis Pleyel",
                    "ligne": "15",
                    "mise_en_service": "2024",
                    "statut": "en travaux",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [2.3536, 48.9236],
                },
            },
            {
                "properties": {
                    "nom_gare": "Noisy-Champs",
                    "ligne": "16",
                    "mise_en_service": "2025",
                    "statut": "en travaux",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [2.6478, 48.8402],
                },
            },
        ],
    }


@pytest.fixture
def geojson_noms_alternatifs() -> dict:
    """GeoJSON avec des noms de properties
    alternatifs (variantes de la source)."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "properties": {
                    "name": "Champigny Centre",  # 'name' au lieu de 'nom_gare'
                    "indice_lig": "15",  # 'indice_lig' au lieu de 'ligne'
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [2.5149, 48.8167],
                },
            },
        ],
    }


@pytest.fixture
def geojson_sans_coordonnees() -> dict:
    """GeoJSON avec une gare sans coordonnées — doit être filtrée."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "properties": {"nom_gare": "Gare valide", "ligne": "15"},
                "geometry": {"type": "Point", "coordinates": [2.35, 48.85]},
            },
            {
                "properties": {"nom_gare": "Gare sans coords", "ligne": "16"},
                "geometry": {"type": "Point", "coordinates": [None, None]},
            },
        ],
    }


@pytest.fixture
def geojson_vide() -> dict:
    """GeoJSON sans aucune feature — doit lever ValueError."""
    return {"type": "FeatureCollection", "features": []}


# ─────────────────────────────────────────────
# Tests parse_gpe
# ─────────────────────────────────────────────


class TestParseGpe:

    def test_retourne_dataframe(self, geojson_valide: dict) -> None:
        """parse_gpe doit retourner un DataFrame pandas."""
        result = parse_gpe(geojson_valide)
        assert isinstance(result, pd.DataFrame)

    def test_nombre_lignes(self, geojson_valide: dict) -> None:
        """On doit avoir autant de lignes que de gares dans le GeoJSON."""
        result = parse_gpe(geojson_valide)
        assert len(result) == 2

    def test_colonnes_presentes(self, geojson_valide: dict) -> None:
        """Le DataFrame doit contenir les colonnes métier attendues."""
        result = parse_gpe(geojson_valide)
        colonnes_attendues = {
            "nom_gare",
            "ligne",
            "longitude",
            "latitude",
            "mise_en_service",
            "statut",
        }
        assert colonnes_attendues.issubset(set(result.columns))

    def test_coordonnees_correctes(self, geojson_valide: dict) -> None:
        """Les coordonnées doivent correspondre à celles du GeoJSON source."""
        result = parse_gpe(geojson_valide)
        # GeoJSON : [longitude, latitude]
        assert result.iloc[0]["longitude"] == pytest.approx(2.3536)
        assert result.iloc[0]["latitude"] == pytest.approx(48.9236)

    def test_noms_alternatifs(self, geojson_noms_alternatifs: dict) -> None:
        """parse_gpe doit gérer les variantes de noms de properties."""
        result = parse_gpe(geojson_noms_alternatifs)
        assert result.iloc[0]["nom_gare"] == "Champigny Centre"
        assert result.iloc[0]["ligne"] == "15"

    def test_filtre_coordonnees_manquantes(
        self, geojson_sans_coordonnees: dict
    ) -> None:
        """Les gares sans coordonnées GPS doivent être supprimées."""
        result = parse_gpe(geojson_sans_coordonnees)
        assert len(result) == 1
        assert result.iloc[0]["nom_gare"] == "Gare valide"

    def test_geojson_vide_leve_erreur(self, geojson_vide: dict) -> None:
        """Un GeoJSON sans feature doit lever ValueError."""
        with pytest.raises(ValueError, match="Aucune gare trouvée"):
            parse_gpe(geojson_vide)

    def test_valeurs_nom_gare(self, geojson_valide: dict) -> None:
        """Les noms de gares doivent correspondre aux données source."""
        result = parse_gpe(geojson_valide)
        noms = result["nom_gare"].tolist()
        assert "Saint-Denis Pleyel" in noms
        assert "Noisy-Champs" in noms


# ─────────────────────────────────────────────
# Tests download_gpe
# ─────────────────────────────────────────────


class TestDownloadGpe:

    def test_retourne_dict(self) -> None:
        """download_gpe doit retourner un dictionnaire (GeoJSON parsé)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"type": "FeatureCollection", "features": []}
        mock_response.raise_for_status.return_value = None

        with patch("ingestion.fetch_gpe.requests.get", return_value=mock_response):
            result = download_gpe("http://fake-url.com/gpe.geojson")

        assert isinstance(result, dict)
        assert "features" in result

    def test_leve_erreur_si_http_400(self) -> None:
        """download_gpe doit lever HTTPError si le serveur répond en erreur."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")

        with patch("ingestion.fetch_gpe.requests.get", return_value=mock_response):
            with pytest.raises(Exception):
                download_gpe("http://fake-url.com/gpe.geojson")
