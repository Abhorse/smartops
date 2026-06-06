from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_async_database_url(database_url: str) -> tuple[str, dict[str, object]]:
    """Prepare a SQLAlchemy async URL for asyncpg.

    Neon and other providers often append libpq query params such as
    ``sslmode=require`` and ``channel_binding=require``. asyncpg rejects those
    as connect() kwargs, so strip them and map sslmode to ``connect_args``.
    """
    if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    parsed = urlparse(database_url)
    if "+asyncpg" not in parsed.scheme:
        return database_url, {}

    query = parse_qs(parsed.query, keep_blank_values=True)
    connect_args: dict[str, object] = {}

    sslmode = (query.pop("sslmode", ["require"]) or ["require"])[0]
    query.pop("channel_binding", None)

    if sslmode and sslmode != "disable":
        connect_args["ssl"] = True

    clean_query = urlencode({key: values[0] for key, values in query.items() if values and values[0]})
    clean_url = urlunparse(parsed._replace(query=clean_query))
    return clean_url, connect_args
