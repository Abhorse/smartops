from app.core.database_url import normalize_async_database_url


def test_strips_libpq_params_for_asyncpg():
    raw = (
        "postgresql+asyncpg://user:pass@ep-test-pooler.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )
    url, connect_args = normalize_async_database_url(raw)

    assert "sslmode" not in url
    assert "channel_binding" not in url
    assert connect_args == {"ssl": True}


def test_converts_postgresql_scheme_to_asyncpg():
    raw = "postgresql://user:pass@localhost:5432/smartops?sslmode=require"
    url, connect_args = normalize_async_database_url(raw)

    assert url.startswith("postgresql+asyncpg://")
    assert connect_args == {"ssl": True}
