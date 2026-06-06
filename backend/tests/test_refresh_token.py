import pytest


@pytest.mark.asyncio
async def test_refresh_token(client):
    login = await client.post(
        "/api/v1/auth/dev-login",
        json={
            "email": "refresh@example.com",
            "full_name": "Refresh User",
            "device_id": "device-refresh",
            "device_name": "Test Phone",
        },
    )
    assert login.status_code == 200
    tokens = login.json()["data"]

    refresh = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": tokens["refresh_token"],
            "device_id": "device-refresh",
        },
    )
    assert refresh.status_code == 200
    refreshed = refresh.json()["data"]
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]
    assert refreshed["refresh_token"] != tokens["refresh_token"]
