import pytest


@pytest.mark.asyncio
async def test_vehicle_and_transport_expense_sync(client):
    login = await client.post(
        "/api/v1/auth/dev-login",
        json={
            "email": "fleet@example.com",
            "full_name": "Fleet Owner",
            "device_id": "device-fleet-1",
            "device_name": "Test Phone",
        },
    )
    assert login.status_code == 200
    access_token = login.json()["data"]["access_token"]

    org = await client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": "Transport Co",
            "business_type": "transport",
            "city": "Delhi",
            "language": "en",
        },
    )
    assert org.status_code == 201
    org_id = org.json()["data"]["id"]
    headers = {"Authorization": f"Bearer {access_token}", "X-Organization-Id": org_id}

    vehicle_id = "11111111-1111-4111-8111-111111111111"
    expense_id = "22222222-2222-4222-8222-222222222222"

    push_vehicle = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-fleet-1",
            "client_schema_version": 1,
            "changes": {
                "vehicles": [
                    {
                        "id": vehicle_id,
                        "operation": "create",
                        "data": {
                            "name": "Truck 1",
                            "registration_number": "MH12AB1234",
                            "loading_charge_per_unit": 500,
                            "unloading_charge_per_unit": 400,
                            "default_labour_employee_ids": '["emp-a","emp-b"]',
                            "is_active": True,
                        },
                        "client_updated_at": "2026-06-05T10:00:00Z",
                    }
                ]
            },
        },
    )
    assert push_vehicle.status_code == 200
    assert vehicle_id in push_vehicle.json()["accepted"]

    push_expense = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-fleet-1",
            "client_schema_version": 1,
            "changes": {
                "expenses": [
                    {
                        "id": expense_id,
                        "operation": "create",
                        "data": {
                            "amount": 1800,
                            "expense_date": "2026-06-05",
                            "description": "Trip loading/unloading",
                            "payment_method": "cash",
                            "vehicle_id": vehicle_id,
                            "transport_type": "loading_unloading",
                            "loading_count": 2,
                            "unloading_count": 2,
                            "labour_employee_ids": '["emp-a","emp-b"]',
                        },
                        "client_updated_at": "2026-06-05T10:05:00Z",
                    }
                ]
            },
        },
    )
    assert push_expense.status_code == 200
    assert expense_id in push_expense.json()["accepted"]

    pull = await client.get("/api/v1/sync/pull", headers=headers)
    assert pull.status_code == 200
    changes = pull.json()["data"]["changes"]

    vehicles = [item for item in changes["vehicles"] if item["id"] == vehicle_id]
    assert vehicles
    assert vehicles[0]["data"]["name"] == "Truck 1"

    expenses = [item for item in changes["expenses"] if item["id"] == expense_id]
    assert expenses
    assert expenses[0]["data"]["vehicle_id"] == vehicle_id
    assert expenses[0]["data"]["transport_type"] == "loading_unloading"
    assert expenses[0]["data"]["loading_count"] == 2
