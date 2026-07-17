"""Tests for application configuration."""

from app.core.config import Settings


def test_default_settings_target_local_docker_services() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.ai_enabled is False
    assert settings.sqlalchemy_database_url == (
        "postgresql+psycopg://retail_user:change_me@db:5432/retailpulse"
    )
