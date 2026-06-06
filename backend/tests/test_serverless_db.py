import os

from app.core.database import should_run_startup_db_init


def test_startup_db_init_skipped_on_vercel(monkeypatch):
    monkeypatch.delenv("SKIP_STARTUP_DB_INIT", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert should_run_startup_db_init() is False


def test_startup_db_init_skipped_when_env_set(monkeypatch):
    monkeypatch.setenv("SKIP_STARTUP_DB_INIT", "true")
    monkeypatch.delenv("VERCEL", raising=False)
    assert should_run_startup_db_init() is False


def test_startup_db_init_runs_locally(monkeypatch):
    monkeypatch.delenv("SKIP_STARTUP_DB_INIT", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert should_run_startup_db_init() is True
