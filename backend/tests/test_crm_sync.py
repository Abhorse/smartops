import pytest


@pytest.mark.asyncio
async def test_crm_sync_and_linked_balances(client):
    login = await client.post(
        "/api/v1/auth/dev-login",
        json={
            "email": "crm@example.com",
            "full_name": "CRM Owner",
            "device_id": "device-crm-1",
            "device_name": "Test Phone",
        },
    )
    assert login.status_code == 200
    access_token = login.json()["data"]["access_token"]

    org = await client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": "CRM Store",
            "business_type": "retail",
            "city": "Jaipur",
            "language": "en",
        },
    )
    assert org.status_code == 201
    org_id = org.json()["data"]["id"]
    headers = {"Authorization": f"Bearer {access_token}", "X-Organization-Id": org_id}

    push_customer = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-crm-1",
            "client_schema_version": 1,
            "changes": {
                "customers": [
                    {
                        "id": "customer-1",
                        "operation": "create",
                        "data": {
                            "name": "Suresh Traders",
                            "phone": "9876543210",
                            "address": "Market Road",
                        },
                        "client_updated_at": "2026-06-05T10:00:00Z",
                    }
                ]
            },
        },
    )
    assert push_customer.status_code == 200
    assert "customer-1" in push_customer.json()["accepted"]

    push_vendor = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-crm-1",
            "client_schema_version": 1,
            "changes": {
                "vendors": [
                    {
                        "id": "vendor-1",
                        "operation": "create",
                        "data": {
                            "name": "Grain Supplier",
                            "phone": "9123456780",
                        },
                        "client_updated_at": "2026-06-05T10:05:00Z",
                    }
                ]
            },
        },
    )
    assert push_vendor.status_code == 200

    push_revenue = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-crm-1",
            "client_schema_version": 1,
            "changes": {
                "revenue": [
                    {
                        "id": "revenue-crm-1",
                        "operation": "create",
                        "data": {
                            "amount": 2500,
                            "revenue_date": "2026-06-05",
                            "description": "Credit sale",
                            "payment_method": "cash",
                            "customer_id": "customer-1",
                        },
                        "client_updated_at": "2026-06-05T11:00:00Z",
                    }
                ]
            },
        },
    )
    assert push_revenue.status_code == 200

    push_expense = await client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": "device-crm-1",
            "client_schema_version": 1,
            "changes": {
                "expenses": [
                    {
                        "id": "expense-crm-1",
                        "operation": "create",
                        "data": {
                            "amount": 800,
                            "expense_date": "2026-06-05",
                            "description": "Stock purchase",
                            "payment_method": "cash",
                            "vendor_id": "vendor-1",
                        },
                        "client_updated_at": "2026-06-05T11:30:00Z",
                    }
                ]
            },
        },
    )
    assert push_expense.status_code == 200

    pull = await client.get("/api/v1/sync/pull", headers=headers)
    customers = pull.json()["data"]["changes"]["customers"]
    customer = next(item for item in customers if item["id"] == "customer-1")
    assert customer["data"]["outstanding_balance"] == 2500

    vendors = pull.json()["data"]["changes"]["vendors"]
    vendor = next(item for item in vendors if item["id"] == "vendor-1")
    assert vendor["data"]["outstanding_balance"] == 800
