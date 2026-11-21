from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import create_app
from src.infraestructure.bootstrap import lifespan as lifespan_module
from src.infraestructure.persistence.database_provider import DatabaseSettings


@pytest.fixture
def startup(monkeypatch):
    """
    Mocks engine selection and schema creation, and records what the lifespan asked for.
    """
    recorder = MagicMock()
    recorder.engine = MagicMock(name="engine")
    recorder.provide_engine.return_value = recorder.engine
    monkeypatch.setattr(lifespan_module, "provide_engine", recorder.provide_engine)
    monkeypatch.setattr(lifespan_module, "create_schema", recorder.create_schema)
    return recorder


def test_startup_uses_the_given_settings_creates_schema_and_publishes_session_factory(startup):
    settings = DatabaseSettings(_env_file=None, url="postgresql://u:p@db/app")
    app = create_app(settings)

    with TestClient(app):
        startup.provide_engine.assert_called_once_with(settings)
        startup.create_schema.assert_called_once_with(startup.engine)
        assert app.state.db_engine is startup.engine
        assert app.state.session_factory.kw["bind"] is startup.engine
        startup.engine.dispose.assert_not_called()

    startup.engine.dispose.assert_called_once()


def test_startup_reads_settings_from_environment_when_none_given(startup, monkeypatch):
    monkeypatch.setenv("DATABASE_NAME", "from_env")

    with TestClient(create_app()):
        (settings,), _ = startup.provide_engine.call_args
        assert isinstance(settings, DatabaseSettings)
        assert settings.name == "from_env"


def test_engine_is_released_if_schema_creation_fails(startup):
    startup.create_schema.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        with TestClient(create_app()):
            pass

    startup.engine.dispose.assert_called_once()
