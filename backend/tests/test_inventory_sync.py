import pytest


@pytest.mark.asyncio
async def test_inventory_sync_round_trip(client):
    login = await client.post(
        "/api/v1/auth/dev-login",
        json={
            "email": "inventory@example.com",
            "full_name": "Inventory Owner",
            "device_id": "device-inv-1",
            "device_name": "Test Phone",
        },
    )
    assert login.status_code == 200
    access_token = login.json()["data"]["access_token"]

    org = await client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": "Inventory Store",
            "business_type": "retail",
            "city": "Jaipur",
            "language": "en",
        },
    )
    assert org.status_code == 201
    org_id = org.json()["data"]["id"]
    headers = {"Authorization": f"Bearer {access_token}", "X-Organization-Id": org_id}

    pull = await client.get("/api/v1/sync/pull", headers=headers)
    assert pull.status_code == 200
    categories = pull.json()["data"]["changes"]["product_categories"]
    assert len(categories) == 4

    push_product = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-inv-1",
            "client_schema_version": 1,
            "changes": {
                "products": [
                    {
                        "id": "product-rice",
                        "operation": "create",
                        "data": {
                            "name": "Rice 25kg",
                            "sku": "RICE-25",
                            "unit": "pcs",
                            "current_stock": 0,
                            "low_stock_threshold": 5,
                            "cost_price": 900,
                            "selling_price": 1200,
                        },
                        "client_updated_at": "2026-06-05T10:00:00Z",
                    }
                ]
            },
        },
    )
    assert push_product.status_code == 200
    assert "product-rice" in push_product.json()["accepted"]

    push_stock_in = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-inv-1",
            "client_schema_version": 1,
            "changes": {
                "stock_movements": [
                    {
                        "id": "movement-1",
                        "operation": "create",
                        "data": {
                            "product_id": "product-rice",
                            "movement_type": "in",
                            "quantity": 20,
                            "movement_date": "2026-06-05",
                            "notes": "Opening stock",
                        },
                        "client_updated_at": "2026-06-05T10:30:00Z",
                    }
                ]
            },
        },
    )
    assert push_stock_in.status_code == 200
    assert "movement-1" in push_stock_in.json()["accepted"]

    pull_after = await client.get("/api/v1/sync/pull", headers=headers)
    products = pull_after.json()["data"]["changes"]["products"]
    rice = next(item for item in products if item["id"] == "product-rice")
    assert rice["data"]["current_stock"] == 20

    movements = pull_after.json()["data"]["changes"]["stock_movements"]
    assert any(item["id"] == "movement-1" for item in movements)

    push_stock_out = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-inv-1",
            "client_schema_version": 1,
            "changes": {
                "stock_movements": [
                    {
                        "id": "movement-2",
                        "operation": "create",
                        "data": {
                            "product_id": "product-rice",
                            "movement_type": "out",
                            "quantity": 3,
                            "movement_date": "2026-06-05",
                        },
                        "client_updated_at": "2026-06-05T11:00:00Z",
                    }
                ]
            },
        },
    )
    assert push_stock_out.status_code == 200

    pull_final = await client.get("/api/v1/sync/pull", headers=headers)
    rice_final = next(item for item in pull_final.json()["data"]["changes"]["products"] if item["id"] == "product-rice")
    assert rice_final["data"]["current_stock"] == 17

    push_delete = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-inv-1",
            "client_schema_version": 1,
            "changes": {
                "products": [
                    {
                        "id": "product-rice",
                        "operation": "delete",
                        "client_updated_at": "2026-06-05T12:00:00Z",
                    }
                ]
            },
        },
    )
    assert push_delete.status_code == 200
    assert "product-rice" in push_delete.json()["accepted"]
