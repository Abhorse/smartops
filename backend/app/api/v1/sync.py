from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_organization_id
from app.models import OrganizationMember, User
from app.schemas.common import ApiResponse
from app.schemas.sync import SyncPullResponse, SyncPushRequest, SyncPushResponse
from app.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


async def _ensure_membership(session: AsyncSession, user_id: str, organization_id: str) -> None:
    membership = await session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.is_active.is_(True),
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of organization")


@router.post("/push", response_model=SyncPushResponse)
async def sync_push(
    payload: SyncPushRequest,
    organization_id: str = Depends(get_organization_id),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SyncPushResponse:
    await _ensure_membership(session, user.id, organization_id)
    service = SyncService(session)

    accepted: list[str] = []
    rejected: list[dict] = []
    conflicts: list[dict] = []

    expense_changes = [change.model_dump() for change in payload.changes.get("expenses", [])]
    if expense_changes:
        a, r, c = await service.push_expenses(organization_id, user.id, expense_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    revenue_changes = [change.model_dump() for change in payload.changes.get("revenue", [])]
    if revenue_changes:
        a, r, c = await service.push_revenue(organization_id, user.id, revenue_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    employee_changes = [change.model_dump() for change in payload.changes.get("employees", [])]
    if employee_changes:
        a, r, c = await service.push_employees(organization_id, user.id, employee_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    attendance_changes = [change.model_dump() for change in payload.changes.get("attendance", [])]
    if attendance_changes:
        a, r, c = await service.push_attendance(organization_id, user.id, attendance_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    salary_structure_changes = [change.model_dump() for change in payload.changes.get("salary_structures", [])]
    if salary_structure_changes:
        a, r, c = await service.push_salary_structures(organization_id, user.id, salary_structure_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    payroll_run_changes = [change.model_dump() for change in payload.changes.get("payroll_runs", [])]
    if payroll_run_changes:
        a, r, c = await service.push_payroll_runs(organization_id, user.id, payroll_run_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    payroll_line_item_changes = [change.model_dump() for change in payload.changes.get("payroll_line_items", [])]
    if payroll_line_item_changes:
        a, r, c = await service.push_payroll_line_items(organization_id, user.id, payroll_line_item_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    product_changes = [change.model_dump() for change in payload.changes.get("products", [])]
    if product_changes:
        a, r, c = await service.push_products(organization_id, user.id, product_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    stock_movement_changes = [change.model_dump() for change in payload.changes.get("stock_movements", [])]
    if stock_movement_changes:
        a, r, c = await service.push_stock_movements(organization_id, user.id, stock_movement_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    customer_changes = [change.model_dump() for change in payload.changes.get("customers", [])]
    if customer_changes:
        a, r, c = await service.push_customers(organization_id, user.id, customer_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    vendor_changes = [change.model_dump() for change in payload.changes.get("vendors", [])]
    if vendor_changes:
        a, r, c = await service.push_vendors(organization_id, user.id, vendor_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    vehicle_changes = [change.model_dump() for change in payload.changes.get("vehicles", [])]
    if vehicle_changes:
        a, r, c = await service.push_vehicles(organization_id, user.id, vehicle_changes)
        accepted.extend(a)
        rejected.extend(r)
        conflicts.extend(c)

    return SyncPushResponse(
        accepted=accepted,
        rejected=rejected,
        conflicts=conflicts,
        server_timestamp=datetime.now(timezone.utc),
    )


@router.get("/pull", response_model=ApiResponse[SyncPullResponse])
async def sync_pull(
    since: Optional[datetime] = Query(default=None),
    organization_id: str = Depends(get_organization_id),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SyncPullResponse]:
    await _ensure_membership(session, user.id, organization_id)
    service = SyncService(session)

    changes: dict[str, list] = {
        "expense_categories": await service.pull_categories(organization_id),
        "expenses": await service.pull_expenses(organization_id, since),
        "revenue_categories": await service.pull_revenue_categories(organization_id),
        "revenue": await service.pull_revenue(organization_id, since),
        "employees": await service.pull_employees(organization_id, since),
        "attendance": await service.pull_attendance(organization_id, since),
        "salary_structures": await service.pull_salary_structures(organization_id, since),
        "payroll_runs": await service.pull_payroll_runs(organization_id, since),
        "payroll_line_items": await service.pull_payroll_line_items(organization_id, since),
        "product_categories": await service.pull_product_categories(organization_id),
        "products": await service.pull_products(organization_id, since),
        "stock_movements": await service.pull_stock_movements(organization_id, since),
        "customers": await service.pull_customers(organization_id, since),
        "vendors": await service.pull_vendors(organization_id, since),
        "vehicles": await service.pull_vehicles(organization_id, since),
    }

    return ApiResponse(
        data=SyncPullResponse(
            server_timestamp=datetime.now(timezone.utc),
            changes=changes,
        )
    )
