import pytest


@pytest.mark.asyncio
async def test_dev_login_and_create_organization(client):
    login = await client.post(
        "/api/v1/auth/dev-login",
        json={
            "email": "owner@example.com",
            "full_name": "Rajesh Kumar",
            "device_id": "device-123",
            "device_name": "Test Phone",
        },
    )
    assert login.status_code == 200
    tokens = login.json()["data"]
    access_token = tokens["access_token"]
    assert tokens["user"]["email"] == "owner@example.com"

    org = await client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": "Rajesh Grocery",
            "business_type": "grocery",
            "city": "Jaipur",
            "language": "en",
        },
    )
    assert org.status_code == 201
    org_id = org.json()["data"]["id"]

    sync_push = await client.post(
        "/api/v1/sync/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
        json={
            "device_id": "device-123",
            "client_schema_version": 1,
            "changes": {
                "expenses": [
                    {
                        "id": "expense-1",
                        "operation": "create",
                        "data": {
                            "amount": 500,
                            "expense_date": "2026-06-05",
                            "description": "Tea supplies",
                            "payment_method": "cash",
                        },
                        "client_updated_at": "2026-06-05T10:00:00Z",
                    }
                ]
            },
        },
    )
    assert sync_push.status_code == 200
    assert "expense-1" in sync_push.json()["accepted"]

    sync_pull = await client.get(
        "/api/v1/sync/pull",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
    )
    assert sync_pull.status_code == 200
    expenses = sync_pull.json()["data"]["changes"]["expenses"]
    assert len(expenses) == 1
    assert expenses[0]["data"]["amount"] == 500

    revenue_categories = sync_pull.json()["data"]["changes"]["revenue_categories"]
    assert len(revenue_categories) == 3

    sync_push_revenue = await client.post(
        "/api/v1/sync/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
        json={
            "device_id": "device-123",
            "client_schema_version": 1,
            "changes": {
                "revenue": [
                    {
                        "id": "revenue-1",
                        "operation": "create",
                        "data": {
                            "amount": 1200,
                            "revenue_date": "2026-06-05",
                            "description": "Morning sales",
                            "payment_method": "cash",
                        },
                        "client_updated_at": "2026-06-05T11:00:00Z",
                    }
                ]
            },
        },
    )
    assert sync_push_revenue.status_code == 200
    assert "revenue-1" in sync_push_revenue.json()["accepted"]

    sync_pull_after = await client.get(
        "/api/v1/sync/pull",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
    )
    revenue = sync_pull_after.json()["data"]["changes"]["revenue"]
    assert len(revenue) == 1
    assert revenue[0]["data"]["amount"] == 1200

    sync_push_employee = await client.post(
        "/api/v1/sync/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
        json={
            "device_id": "device-123",
            "client_schema_version": 1,
            "changes": {
                "employees": [
                    {
                        "id": "employee-1",
                        "operation": "create",
                        "data": {
                            "full_name": "Ramesh Kumar",
                            "phone": "9876543210",
                            "department": "Sales",
                            "designation": "Sales Assistant",
                            "joining_date": "2026-01-15",
                            "employment_status": "active",
                            "base_salary": 15000,
                        },
                        "client_updated_at": "2026-06-05T12:00:00Z",
                    }
                ]
            },
        },
    )
    assert sync_push_employee.status_code == 200
    assert "employee-1" in sync_push_employee.json()["accepted"]

    employees = (
        await client.get(
            "/api/v1/sync/pull",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Organization-Id": org_id,
            },
        )
    ).json()["data"]["changes"]["employees"]
    assert len(employees) == 1
    assert employees[0]["data"]["full_name"] == "Ramesh Kumar"

    sync_push_attendance = await client.post(
        "/api/v1/sync/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
        json={
            "device_id": "device-123",
            "client_schema_version": 1,
            "changes": {
                "attendance": [
                    {
                        "id": "attendance-1",
                        "operation": "create",
                        "data": {
                            "employee_id": "employee-1",
                            "attendance_date": "2026-06-05",
                            "status": "present",
                            "check_in_time": "2026-06-05T09:00:00+00:00",
                            "check_out_time": "2026-06-05T18:00:00+00:00",
                        },
                        "client_updated_at": "2026-06-05T13:00:00Z",
                    }
                ]
            },
        },
    )
    assert sync_push_attendance.status_code == 200
    assert "attendance-1" in sync_push_attendance.json()["accepted"]

    attendance = (
        await client.get(
            "/api/v1/sync/pull",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Organization-Id": org_id,
            },
        )
    ).json()["data"]["changes"]["attendance"]
    assert len(attendance) == 1
    assert attendance[0]["data"]["status"] == "present"

    sync_push_salary = await client.post(
        "/api/v1/sync/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
        json={
            "device_id": "device-123",
            "client_schema_version": 1,
            "changes": {
                "salary_structures": [
                    {
                        "id": "salary-1",
                        "operation": "create",
                        "data": {
                            "employee_id": "employee-1",
                            "base_salary": 15000,
                            "hra": 3000,
                            "pf_deduction": 1800,
                            "effective_from": "2026-01-15",
                        },
                        "client_updated_at": "2026-06-05T14:00:00Z",
                    }
                ]
            },
        },
    )
    assert sync_push_salary.status_code == 200
    assert "salary-1" in sync_push_salary.json()["accepted"]

    sync_push_payroll_run = await client.post(
        "/api/v1/sync/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
        json={
            "device_id": "device-123",
            "client_schema_version": 1,
            "changes": {
                "payroll_runs": [
                    {
                        "id": "payroll-run-1",
                        "operation": "create",
                        "data": {
                            "period_start": "2026-06-01",
                            "period_end": "2026-06-30",
                            "status": "draft",
                            "total_gross": 18000,
                            "total_deductions": 1800,
                            "total_net": 16200,
                        },
                        "client_updated_at": "2026-06-05T15:00:00Z",
                    }
                ],
                "payroll_line_items": [
                    {
                        "id": "payroll-line-1",
                        "operation": "create",
                        "data": {
                            "payroll_run_id": "payroll-run-1",
                            "employee_id": "employee-1",
                            "base_salary": 15000,
                            "total_allowances": 3000,
                            "total_deductions": 1800,
                            "net_salary": 16200,
                            "days_worked": 1,
                            "days_in_period": 30,
                        },
                        "client_updated_at": "2026-06-05T15:00:00Z",
                    }
                ],
            },
        },
    )
    assert sync_push_payroll_run.status_code == 200
    assert "payroll-run-1" in sync_push_payroll_run.json()["accepted"]
    assert "payroll-line-1" in sync_push_payroll_run.json()["accepted"]

    payroll_pull = (
        await client.get(
            "/api/v1/sync/pull",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Organization-Id": org_id,
            },
        )
    ).json()["data"]["changes"]
    assert len(payroll_pull["salary_structures"]) == 1
    assert payroll_pull["salary_structures"][0]["data"]["base_salary"] == 15000
    assert len(payroll_pull["payroll_runs"]) == 1
    assert payroll_pull["payroll_runs"][0]["data"]["status"] == "draft"
    assert len(payroll_pull["payroll_line_items"]) == 1

    sync_mark_paid = await client.post(
        "/api/v1/sync/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
        json={
            "device_id": "device-123",
            "client_schema_version": 1,
            "changes": {
                "payroll_runs": [
                    {
                        "id": "payroll-run-1",
                        "operation": "update",
                        "data": {
                            "period_start": "2026-06-01",
                            "period_end": "2026-06-30",
                            "status": "paid",
                            "total_gross": 18000,
                            "total_deductions": 1800,
                            "total_net": 16200,
                        },
                        "client_updated_at": "2026-06-05T16:00:00Z",
                    }
                ]
            },
        },
    )
    assert sync_mark_paid.status_code == 200
    assert "payroll-run-1" in sync_mark_paid.json()["accepted"]

    sync_edit_paid = await client.post(
        "/api/v1/sync/push",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Organization-Id": org_id,
        },
        json={
            "device_id": "device-123",
            "client_schema_version": 1,
            "changes": {
                "payroll_line_items": [
                    {
                        "id": "payroll-line-1",
                        "operation": "update",
                        "data": {
                            "payroll_run_id": "payroll-run-1",
                            "employee_id": "employee-1",
                            "base_salary": 15000,
                            "total_allowances": 3000,
                            "total_deductions": 1800,
                            "net_salary": 99999,
                            "days_worked": 1,
                            "days_in_period": 30,
                        },
                        "client_updated_at": "2026-06-05T17:00:00Z",
                    }
                ]
            },
        },
    )
    assert sync_edit_paid.status_code == 200
    rejected = sync_edit_paid.json()["rejected"]
    assert any(item["code"] == "PAYROLL_FINALIZED" for item in rejected)
