"""
Fixtures partagées des tests d'intégration.

Tout test qui ÉCRIT en base doit utiliser `test_engine` : une base
PostgreSQL temporaire lancée par pytest-postgresql, jamais la base Docker.

Prérequis : PostgreSQL et PostGIS installés en local (init.sql crée
l'extension postgis).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from psycopg import Connection
from pytest_postgresql import factories
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine

INIT_SQL = Path(__file__).resolve().parents[2] / "db" / "init.sql"

# Serveur temporaire : init.sql est chargé UNE fois dans une base modèle,
# puis chaque test reçoit une copie neuve de cette base.
postgresql_proc = factories.postgresql_proc(load=[INIT_SQL])
postgresql = factories.postgresql("postgresql_proc")


@pytest.fixture
def test_engine(postgresql: Connection) -> Iterator[Engine]:
    """Engine SQLAlchemy vers la base temporaire du test.

    L'URL reprend le PORT de la base temporaire : sans lui, la connexion
    partirait sur le port par défaut (5432), c'est-à-dire la base Docker.
    """
    info = postgresql.info
    url = URL.create(
        "postgresql+psycopg2",
        username=info.user,
        password=info.password or None,
        host=info.host,
        port=info.port,
        database=info.dbname,
    )
    engine = create_engine(url)
    yield engine
    engine.dispose()
