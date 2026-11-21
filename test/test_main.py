import pytest

from main import database_settings_from_args, parse_startup_args


def test_cli_arguments_become_database_settings():
    args = parse_startup_args([
        "--database-url", "postgresql://u:p@db/app", "--database-name", "other", "--no-memory-fallback",
        "--port", "9000",
    ])

    settings = database_settings_from_args(args)

    assert settings.url.get_secret_value() == "postgresql://u:p@db/app"
    assert settings.name == "other"
    assert settings.fallback_to_memory is False
    assert args.port == 9000


@pytest.mark.parametrize("cli_args, expected_override", [
    (["--database-url", "postgresql://u:p@cli-db/app"], ("url", "postgresql://u:p@cli-db/app")),
    (["--database-name", "cli_db"], ("name", "cli_db")),
    (["--no-memory-fallback"], ("fallback_to_memory", False)),
])
def test_omitted_cli_arguments_keep_environment_values(monkeypatch, cli_args, expected_override):
    environment = {"url": "postgresql://u:p@env-db/app", "name": "env_db", "fallback_to_memory": False}
    monkeypatch.setenv("DATABASE_URL", environment["url"])
    monkeypatch.setenv("DATABASE_NAME", environment["name"])
    monkeypatch.setenv("DATABASE_FALLBACK_TO_MEMORY", "false")

    settings = database_settings_from_args(parse_startup_args(cli_args))

    expected = environment | dict([expected_override])
    assert settings.url.get_secret_value() == expected["url"]
    assert settings.name == expected["name"]
    assert settings.fallback_to_memory is expected["fallback_to_memory"]


def test_defaults_without_arguments():
    args = parse_startup_args([])

    settings = database_settings_from_args(args)

    assert (args.host, args.port) == ("127.0.0.1", 8000)
    assert settings.url is None
    assert settings.fallback_to_memory is True
