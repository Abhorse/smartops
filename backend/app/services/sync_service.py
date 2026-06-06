from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttendanceRecord,
    Customer,
    Employee,
    Expense,
    ExpenseCategory,
    PayrollLineItem,
    PayrollRun,
    Product,
    ProductCategory,
    RevenueCategory,
    RevenueEntry,
    SalaryStructure,
    StockMovement,
    Vehicle,
    Vendor,
)


class SyncService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def push_expenses(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "expenses", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                expense = await self.session.get(Expense, record_id)
                if expense and expense.organization_id == organization_id:
                    vendor_id = expense.vendor_id
                    expense.deleted_at = datetime.now(timezone.utc)
                    expense.version += 1
                    if vendor_id:
                        await self._refresh_vendor_balance(vendor_id)
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            amount = data.get("amount")
            expense_date_raw = data.get("expense_date")
            if amount is None or expense_date_raw is None:
                rejected.append(
                    {
                        "entity": "expenses",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "amount and expense_date are required",
                    }
                )
                continue

            try:
                amount_value = float(amount)
                if amount_value <= 0:
                    raise ValueError
                expense_date = date.fromisoformat(str(expense_date_raw)[:10])
            except ValueError:
                rejected.append(
                    {
                        "entity": "expenses",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid amount or expense_date",
                    }
                )
                continue

            category_id = data.get("category_id")
            if category_id:
                category = await self.session.get(ExpenseCategory, category_id)
                if category is None or category.organization_id != organization_id:
                    category_id = None

            if not category_id:
                default_category = await self.session.scalar(
                    select(ExpenseCategory).where(
                        ExpenseCategory.organization_id == organization_id,
                        ExpenseCategory.deleted_at.is_(None),
                    )
                )
                category_id = default_category.id if default_category else None

            vendor_id = data.get("vendor_id")
            is_self_vendor = bool(data.get("is_self_vendor", False))
            if is_self_vendor:
                vendor_id = None
            elif vendor_id:
                vendor = await self.session.get(Vendor, vendor_id)
                if vendor is None or vendor.organization_id != organization_id:
                    vendor_id = None

            customer_id = data.get("customer_id")
            if customer_id:
                customer = await self.session.get(Customer, customer_id)
                if customer is None or customer.organization_id != organization_id:
                    customer_id = None

            billed_amount = self._optional_float(data.get("billed_amount"))

            vehicle_id = data.get("vehicle_id")
            if vehicle_id:
                vehicle = await self.session.get(Vehicle, vehicle_id)
                if vehicle is None or vehicle.organization_id != organization_id:
                    vehicle_id = None

            driver_employee_id = data.get("driver_employee_id")
            if driver_employee_id:
                driver = await self.session.get(Employee, driver_employee_id)
                if driver is None or driver.organization_id != organization_id:
                    driver_employee_id = None

            transport_type = data.get("transport_type")
            loading_count = self._int_or_zero(data.get("loading_count"))
            unloading_count = self._int_or_zero(data.get("unloading_count"))
            labour_employee_ids = data.get("labour_employee_ids")

            expense = await self.session.get(Expense, record_id)
            previous_vendor_id = expense.vendor_id if expense else None
            if expense is None:
                expense = Expense(
                    id=record_id,
                    organization_id=organization_id,
                    category_id=category_id,
                    vendor_id=vendor_id,
                    customer_id=customer_id,
                    vehicle_id=vehicle_id,
                    transport_type=transport_type,
                    loading_count=loading_count,
                    unloading_count=unloading_count,
                    driver_employee_id=driver_employee_id,
                    labour_employee_ids=labour_employee_ids,
                    billed_amount=billed_amount,
                    is_self_vendor=is_self_vendor,
                    amount=amount_value,
                    expense_date=expense_date,
                    description=data.get("description"),
                    payment_method=data.get("payment_method"),
                    created_by=user_id,
                )
                self.session.add(expense)
            elif expense.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "expenses",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Expense belongs to another organization",
                    }
                )
                continue
            else:
                expense.amount = amount_value
                expense.expense_date = expense_date
                expense.description = data.get("description")
                expense.payment_method = data.get("payment_method")
                expense.category_id = category_id
                expense.vendor_id = vendor_id
                expense.customer_id = customer_id
                expense.vehicle_id = vehicle_id
                expense.transport_type = transport_type
                expense.loading_count = loading_count
                expense.unloading_count = unloading_count
                expense.driver_employee_id = driver_employee_id
                expense.labour_employee_ids = labour_employee_ids
                expense.billed_amount = billed_amount
                expense.is_self_vendor = is_self_vendor
                expense.version += 1
                expense.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                expense.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            if vendor_id:
                await self._refresh_vendor_balance(vendor_id)
            if previous_vendor_id and previous_vendor_id != vendor_id:
                await self._refresh_vendor_balance(previous_vendor_id)

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_expenses(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(Expense).where(Expense.organization_id == organization_id)
        if since is not None:
            query = query.where(Expense.updated_at >= since)
        result = await self.session.execute(query.order_by(Expense.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for expense in result.scalars():
            operation = "delete" if expense.deleted_at else "update"
            records.append(
                {
                    "id": expense.id,
                    "operation": operation,
                    "data": {
                        "id": expense.id,
                        "organization_id": expense.organization_id,
                        "category_id": expense.category_id,
                        "amount": float(expense.amount),
                        "currency_code": expense.currency_code,
                        "expense_date": expense.expense_date.isoformat(),
                        "description": expense.description,
                        "payment_method": expense.payment_method,
                        "vendor_id": expense.vendor_id,
                        "customer_id": expense.customer_id,
                        "vehicle_id": expense.vehicle_id,
                        "transport_type": expense.transport_type,
                        "loading_count": expense.loading_count,
                        "unloading_count": expense.unloading_count,
                        "driver_employee_id": expense.driver_employee_id,
                        "labour_employee_ids": expense.labour_employee_ids,
                        "billed_amount": float(expense.billed_amount) if expense.billed_amount is not None else None,
                        "is_self_vendor": expense.is_self_vendor,
                        "version": expense.version,
                    },
                    "version": expense.version,
                    "updated_at": expense.updated_at.isoformat(),
                    "deleted_at": expense.deleted_at.isoformat() if expense.deleted_at else None,
                }
            )
        return records

    async def pull_categories(self, organization_id: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.organization_id == organization_id,
                ExpenseCategory.deleted_at.is_(None),
            )
        )
        return [
            {
                "id": category.id,
                "operation": "update",
                "data": {
                    "id": category.id,
                    "organization_id": category.organization_id,
                    "name": category.name,
                    "color": category.color,
                    "is_default": category.is_default,
                },
                "version": category.version,
                "updated_at": category.updated_at.isoformat(),
                "deleted_at": None,
            }
            for category in result.scalars()
        ]

    async def push_revenue(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "revenue", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                entry = await self.session.get(RevenueEntry, record_id)
                if entry and entry.organization_id == organization_id:
                    customer_id = entry.customer_id
                    entry.deleted_at = datetime.now(timezone.utc)
                    entry.version += 1
                    if customer_id:
                        await self._refresh_customer_balance(customer_id)
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            amount = data.get("amount")
            revenue_date_raw = data.get("revenue_date")
            if amount is None or revenue_date_raw is None:
                rejected.append(
                    {
                        "entity": "revenue",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "amount and revenue_date are required",
                    }
                )
                continue

            try:
                amount_value = float(amount)
                if amount_value <= 0:
                    raise ValueError
                revenue_date = date.fromisoformat(str(revenue_date_raw)[:10])
            except ValueError:
                rejected.append(
                    {
                        "entity": "revenue",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid amount or revenue_date",
                    }
                )
                continue

            category_id = data.get("category_id")
            if category_id:
                category = await self.session.get(RevenueCategory, category_id)
                if category is None or category.organization_id != organization_id:
                    category_id = None

            if not category_id:
                default_category = await self.session.scalar(
                    select(RevenueCategory).where(
                        RevenueCategory.organization_id == organization_id,
                        RevenueCategory.deleted_at.is_(None),
                    )
                )
                category_id = default_category.id if default_category else None

            customer_id = data.get("customer_id")
            if customer_id:
                customer = await self.session.get(Customer, customer_id)
                if customer is None or customer.organization_id != organization_id:
                    customer_id = None

            entry = await self.session.get(RevenueEntry, record_id)
            previous_customer_id = entry.customer_id if entry else None
            if entry is None:
                entry = RevenueEntry(
                    id=record_id,
                    organization_id=organization_id,
                    category_id=category_id,
                    customer_id=customer_id,
                    amount=amount_value,
                    revenue_date=revenue_date,
                    description=data.get("description"),
                    payment_method=data.get("payment_method"),
                    created_by=user_id,
                )
                self.session.add(entry)
            elif entry.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "revenue",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Revenue entry belongs to another organization",
                    }
                )
                continue
            else:
                entry.amount = amount_value
                entry.revenue_date = revenue_date
                entry.description = data.get("description")
                entry.payment_method = data.get("payment_method")
                entry.category_id = category_id
                entry.customer_id = customer_id
                entry.version += 1
                entry.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                entry.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            if customer_id:
                await self._refresh_customer_balance(customer_id)
            if previous_customer_id and previous_customer_id != customer_id:
                await self._refresh_customer_balance(previous_customer_id)

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_revenue(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(RevenueEntry).where(RevenueEntry.organization_id == organization_id)
        if since is not None:
            query = query.where(RevenueEntry.updated_at >= since)
        result = await self.session.execute(query.order_by(RevenueEntry.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for entry in result.scalars():
            operation = "delete" if entry.deleted_at else "update"
            records.append(
                {
                    "id": entry.id,
                    "operation": operation,
                    "data": {
                        "id": entry.id,
                        "organization_id": entry.organization_id,
                        "category_id": entry.category_id,
                        "amount": float(entry.amount),
                        "currency_code": entry.currency_code,
                        "revenue_date": entry.revenue_date.isoformat(),
                        "description": entry.description,
                        "payment_method": entry.payment_method,
                        "customer_id": entry.customer_id,
                        "version": entry.version,
                    },
                    "version": entry.version,
                    "updated_at": entry.updated_at.isoformat(),
                    "deleted_at": entry.deleted_at.isoformat() if entry.deleted_at else None,
                }
            )
        return records

    async def pull_revenue_categories(self, organization_id: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(RevenueCategory).where(
                RevenueCategory.organization_id == organization_id,
                RevenueCategory.deleted_at.is_(None),
            )
        )
        return [
            {
                "id": category.id,
                "operation": "update",
                "data": {
                    "id": category.id,
                    "organization_id": category.organization_id,
                    "name": category.name,
                    "is_default": category.is_default,
                },
                "version": category.version,
                "updated_at": category.updated_at.isoformat(),
                "deleted_at": None,
            }
            for category in result.scalars()
        ]

    async def push_employees(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "employees", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                employee = await self.session.get(Employee, record_id)
                if employee and employee.organization_id == organization_id:
                    employee.deleted_at = datetime.now(timezone.utc)
                    employee.employment_status = "inactive"
                    employee.version += 1
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            full_name = data.get("full_name")
            joining_date_raw = data.get("joining_date")
            if not full_name or not joining_date_raw:
                rejected.append(
                    {
                        "entity": "employees",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "full_name and joining_date are required",
                    }
                )
                continue

            try:
                joining_date = date.fromisoformat(str(joining_date_raw)[:10])
            except ValueError:
                rejected.append(
                    {
                        "entity": "employees",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid joining_date",
                    }
                )
                continue

            base_salary = data.get("base_salary")
            base_salary_value = None
            if base_salary is not None:
                try:
                    base_salary_value = float(base_salary)
                    if base_salary_value < 0:
                        raise ValueError
                except ValueError:
                    rejected.append(
                        {
                            "entity": "employees",
                            "id": record_id,
                            "code": "VALIDATION_ERROR",
                            "message": "Invalid base_salary",
                        }
                    )
                    continue

            employment_status = data.get("employment_status") or "active"
            if employment_status not in {"active", "inactive"}:
                employment_status = "active"

            salary_type = data.get("salary_type") or "monthly"
            valid_salary_types = {"monthly", "daily", "per_trip", "hourly"}
            if salary_type not in valid_salary_types:
                salary_type = "monthly"

            employee = await self.session.get(Employee, record_id)
            if employee is None:
                employee = Employee(
                    id=record_id,
                    organization_id=organization_id,
                    full_name=str(full_name).strip(),
                    phone=data.get("phone"),
                    email=data.get("email"),
                    department=data.get("department"),
                    designation=data.get("designation"),
                    joining_date=joining_date,
                    employment_status=employment_status,
                    base_salary=base_salary_value,
                    salary_type=salary_type,
                    notes=data.get("notes"),
                    created_by=user_id,
                )
                self.session.add(employee)
            elif employee.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "employees",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Employee belongs to another organization",
                    }
                )
                continue
            else:
                employee.full_name = str(full_name).strip()
                employee.phone = data.get("phone")
                employee.email = data.get("email")
                employee.department = data.get("department")
                employee.designation = data.get("designation")
                employee.joining_date = joining_date
                employee.employment_status = employment_status
                employee.base_salary = base_salary_value
                employee.salary_type = salary_type
                employee.notes = data.get("notes")
                employee.version += 1
                employee.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                employee.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_employees(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(Employee).where(Employee.organization_id == organization_id)
        if since is not None:
            query = query.where(Employee.updated_at >= since)
        result = await self.session.execute(query.order_by(Employee.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for employee in result.scalars():
            operation = "delete" if employee.deleted_at else "update"
            records.append(
                {
                    "id": employee.id,
                    "operation": operation,
                    "data": {
                        "id": employee.id,
                        "organization_id": employee.organization_id,
                        "full_name": employee.full_name,
                        "phone": employee.phone,
                        "email": employee.email,
                        "department": employee.department,
                        "designation": employee.designation,
                        "joining_date": employee.joining_date.isoformat(),
                        "employment_status": employee.employment_status,
                        "base_salary": float(employee.base_salary) if employee.base_salary is not None else None,
                        "salary_type": employee.salary_type,
                        "notes": employee.notes,
                        "version": employee.version,
                    },
                    "version": employee.version,
                    "updated_at": employee.updated_at.isoformat(),
                    "deleted_at": employee.deleted_at.isoformat() if employee.deleted_at else None,
                }
            )
        return records

    async def push_attendance(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        valid_statuses = {"present", "absent", "half_day", "on_leave"}

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "attendance", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                record = await self.session.get(AttendanceRecord, record_id)
                if record and record.organization_id == organization_id:
                    record.deleted_at = datetime.now(timezone.utc)
                    record.version += 1
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            employee_id = data.get("employee_id")
            attendance_date_raw = data.get("attendance_date")
            status = data.get("status")
            if not employee_id or not attendance_date_raw or not status:
                rejected.append(
                    {
                        "entity": "attendance",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "employee_id, attendance_date, and status are required",
                    }
                )
                continue

            if status not in valid_statuses:
                rejected.append(
                    {
                        "entity": "attendance",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid status",
                    }
                )
                continue

            employee = await self.session.get(Employee, employee_id)
            if employee is None or employee.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "attendance",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Employee not found",
                    }
                )
                continue

            try:
                attendance_date = date.fromisoformat(str(attendance_date_raw)[:10])
            except ValueError:
                rejected.append(
                    {
                        "entity": "attendance",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid attendance_date",
                    }
                )
                continue

            check_in_time = self._parse_optional_datetime(data.get("check_in_time"))
            check_out_time = self._parse_optional_datetime(data.get("check_out_time"))

            existing_for_day = await self.session.scalar(
                select(AttendanceRecord).where(
                    AttendanceRecord.organization_id == organization_id,
                    AttendanceRecord.employee_id == employee_id,
                    AttendanceRecord.attendance_date == attendance_date,
                    AttendanceRecord.deleted_at.is_(None),
                )
            )

            record = await self.session.get(AttendanceRecord, record_id)
            if record is None and existing_for_day is not None:
                record = existing_for_day
                record_id = existing_for_day.id

            if record is None:
                record = AttendanceRecord(
                    id=record_id,
                    organization_id=organization_id,
                    employee_id=employee_id,
                    attendance_date=attendance_date,
                    status=status,
                    check_in_time=check_in_time,
                    check_out_time=check_out_time,
                    notes=data.get("notes"),
                    created_by=user_id,
                )
                self.session.add(record)
            elif record.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "attendance",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Attendance belongs to another organization",
                    }
                )
                continue
            else:
                record.employee_id = employee_id
                record.attendance_date = attendance_date
                record.status = status
                record.check_in_time = check_in_time
                record.check_out_time = check_out_time
                record.notes = data.get("notes")
                record.version += 1
                record.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                record.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_attendance(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(AttendanceRecord).where(AttendanceRecord.organization_id == organization_id)
        if since is not None:
            query = query.where(AttendanceRecord.updated_at >= since)
        result = await self.session.execute(query.order_by(AttendanceRecord.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for record in result.scalars():
            operation = "delete" if record.deleted_at else "update"
            records.append(
                {
                    "id": record.id,
                    "operation": operation,
                    "data": {
                        "id": record.id,
                        "organization_id": record.organization_id,
                        "employee_id": record.employee_id,
                        "attendance_date": record.attendance_date.isoformat(),
                        "status": record.status,
                        "check_in_time": record.check_in_time.isoformat() if record.check_in_time else None,
                        "check_out_time": record.check_out_time.isoformat() if record.check_out_time else None,
                        "notes": record.notes,
                        "version": record.version,
                    },
                    "version": record.version,
                    "updated_at": record.updated_at.isoformat(),
                    "deleted_at": record.deleted_at.isoformat() if record.deleted_at else None,
                }
            )
        return records

    async def push_salary_structures(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {
                        "entity": "salary_structures",
                        "id": None,
                        "code": "VALIDATION_ERROR",
                        "message": "Missing id",
                    }
                )
                continue

            if operation == "delete":
                structure = await self.session.get(SalaryStructure, record_id)
                if structure and structure.organization_id == organization_id:
                    structure.deleted_at = datetime.now(timezone.utc)
                    structure.version += 1
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            employee_id = data.get("employee_id")
            base_salary = data.get("base_salary")
            effective_from_raw = data.get("effective_from")
            if not employee_id or base_salary is None or not effective_from_raw:
                rejected.append(
                    {
                        "entity": "salary_structures",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "employee_id, base_salary, and effective_from are required",
                    }
                )
                continue

            employee = await self.session.get(Employee, employee_id)
            if employee is None or employee.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "salary_structures",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Employee not found",
                    }
                )
                continue

            try:
                base_salary_value = float(base_salary)
                if base_salary_value < 0:
                    raise ValueError
                effective_from = date.fromisoformat(str(effective_from_raw)[:10])
            except ValueError:
                rejected.append(
                    {
                        "entity": "salary_structures",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid base_salary or effective_from",
                    }
                )
                continue

            effective_to_raw = data.get("effective_to")
            effective_to = None
            if effective_to_raw:
                try:
                    effective_to = date.fromisoformat(str(effective_to_raw)[:10])
                except ValueError:
                    rejected.append(
                        {
                            "entity": "salary_structures",
                            "id": record_id,
                            "code": "VALIDATION_ERROR",
                            "message": "Invalid effective_to",
                        }
                    )
                    continue

            existing_for_employee = await self.session.scalar(
                select(SalaryStructure).where(
                    SalaryStructure.organization_id == organization_id,
                    SalaryStructure.employee_id == employee_id,
                    SalaryStructure.deleted_at.is_(None),
                )
            )

            structure = await self.session.get(SalaryStructure, record_id)
            if structure is None and existing_for_employee is not None:
                structure = existing_for_employee
                record_id = existing_for_employee.id

            if structure is None:
                structure = SalaryStructure(
                    id=record_id,
                    organization_id=organization_id,
                    employee_id=employee_id,
                    base_salary=base_salary_value,
                    hra=self._float_or_zero(data.get("hra")),
                    transport_allowance=self._float_or_zero(data.get("transport_allowance")),
                    other_allowances=self._float_or_zero(data.get("other_allowances")),
                    pf_deduction=self._float_or_zero(data.get("pf_deduction")),
                    esi_deduction=self._float_or_zero(data.get("esi_deduction")),
                    tax_deduction=self._float_or_zero(data.get("tax_deduction")),
                    other_deductions=self._float_or_zero(data.get("other_deductions")),
                    effective_from=effective_from,
                    effective_to=effective_to,
                    created_by=user_id,
                )
                self.session.add(structure)
            elif structure.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "salary_structures",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Salary structure belongs to another organization",
                    }
                )
                continue
            else:
                structure.employee_id = employee_id
                structure.base_salary = base_salary_value
                structure.hra = self._float_or_zero(data.get("hra"))
                structure.transport_allowance = self._float_or_zero(data.get("transport_allowance"))
                structure.other_allowances = self._float_or_zero(data.get("other_allowances"))
                structure.pf_deduction = self._float_or_zero(data.get("pf_deduction"))
                structure.esi_deduction = self._float_or_zero(data.get("esi_deduction"))
                structure.tax_deduction = self._float_or_zero(data.get("tax_deduction"))
                structure.other_deductions = self._float_or_zero(data.get("other_deductions"))
                structure.effective_from = effective_from
                structure.effective_to = effective_to
                structure.version += 1
                structure.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                structure.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_salary_structures(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(SalaryStructure).where(SalaryStructure.organization_id == organization_id)
        if since is not None:
            query = query.where(SalaryStructure.updated_at >= since)
        result = await self.session.execute(query.order_by(SalaryStructure.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for structure in result.scalars():
            operation = "delete" if structure.deleted_at else "update"
            records.append(
                {
                    "id": structure.id,
                    "operation": operation,
                    "data": {
                        "id": structure.id,
                        "organization_id": structure.organization_id,
                        "employee_id": structure.employee_id,
                        "base_salary": float(structure.base_salary),
                        "hra": float(structure.hra),
                        "transport_allowance": float(structure.transport_allowance),
                        "other_allowances": float(structure.other_allowances),
                        "pf_deduction": float(structure.pf_deduction),
                        "esi_deduction": float(structure.esi_deduction),
                        "tax_deduction": float(structure.tax_deduction),
                        "other_deductions": float(structure.other_deductions),
                        "effective_from": structure.effective_from.isoformat(),
                        "effective_to": structure.effective_to.isoformat() if structure.effective_to else None,
                        "version": structure.version,
                    },
                    "version": structure.version,
                    "updated_at": structure.updated_at.isoformat(),
                    "deleted_at": structure.deleted_at.isoformat() if structure.deleted_at else None,
                }
            )
        return records

    async def push_payroll_runs(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        valid_statuses = {"draft", "processed", "paid"}

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "payroll_runs", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                run = await self.session.get(PayrollRun, record_id)
                if run and run.organization_id == organization_id:
                    if run.status == "paid":
                        rejected.append(
                            {
                                "entity": "payroll_runs",
                                "id": record_id,
                                "code": "PAYROLL_FINALIZED",
                                "message": "Cannot delete paid payroll",
                            }
                        )
                        continue
                    run.deleted_at = datetime.now(timezone.utc)
                    run.version += 1
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            period_start_raw = data.get("period_start")
            period_end_raw = data.get("period_end")
            status = data.get("status") or "draft"
            if not period_start_raw or not period_end_raw:
                rejected.append(
                    {
                        "entity": "payroll_runs",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "period_start and period_end are required",
                    }
                )
                continue

            if status not in valid_statuses:
                rejected.append(
                    {
                        "entity": "payroll_runs",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid status",
                    }
                )
                continue

            try:
                period_start = date.fromisoformat(str(period_start_raw)[:10])
                period_end = date.fromisoformat(str(period_end_raw)[:10])
            except ValueError:
                rejected.append(
                    {
                        "entity": "payroll_runs",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid period dates",
                    }
                )
                continue

            run = await self.session.get(PayrollRun, record_id)
            if run is not None and run.organization_id == organization_id and run.status == "paid":
                rejected.append(
                    {
                        "entity": "payroll_runs",
                        "id": record_id,
                        "code": "PAYROLL_FINALIZED",
                        "message": "Payroll is finalized",
                    }
                )
                continue

            if run is None:
                run = PayrollRun(
                    id=record_id,
                    organization_id=organization_id,
                    period_start=period_start,
                    period_end=period_end,
                    status=status,
                    total_gross=self._float_or_zero(data.get("total_gross")),
                    total_deductions=self._float_or_zero(data.get("total_deductions")),
                    total_net=self._float_or_zero(data.get("total_net")),
                    notes=data.get("notes"),
                    created_by=user_id,
                )
                self.session.add(run)
            elif run.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "payroll_runs",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Payroll run belongs to another organization",
                    }
                )
                continue
            else:
                run.period_start = period_start
                run.period_end = period_end
                run.status = status
                run.total_gross = self._float_or_zero(data.get("total_gross"))
                run.total_deductions = self._float_or_zero(data.get("total_deductions"))
                run.total_net = self._float_or_zero(data.get("total_net"))
                run.notes = data.get("notes")
                run.version += 1
                run.updated_at = datetime.now(timezone.utc)

            if status in {"processed", "paid"} and run.processed_at is None:
                run.processed_at = datetime.now(timezone.utc)
                run.processed_by = user_id

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                run.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_payroll_runs(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(PayrollRun).where(PayrollRun.organization_id == organization_id)
        if since is not None:
            query = query.where(PayrollRun.updated_at >= since)
        result = await self.session.execute(query.order_by(PayrollRun.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for run in result.scalars():
            operation = "delete" if run.deleted_at else "update"
            records.append(
                {
                    "id": run.id,
                    "operation": operation,
                    "data": {
                        "id": run.id,
                        "organization_id": run.organization_id,
                        "period_start": run.period_start.isoformat(),
                        "period_end": run.period_end.isoformat(),
                        "status": run.status,
                        "total_gross": float(run.total_gross),
                        "total_deductions": float(run.total_deductions),
                        "total_net": float(run.total_net),
                        "processed_at": run.processed_at.isoformat() if run.processed_at else None,
                        "notes": run.notes,
                        "version": run.version,
                    },
                    "version": run.version,
                    "updated_at": run.updated_at.isoformat(),
                    "deleted_at": run.deleted_at.isoformat() if run.deleted_at else None,
                }
            )
        return records

    async def push_payroll_line_items(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {
                        "entity": "payroll_line_items",
                        "id": None,
                        "code": "VALIDATION_ERROR",
                        "message": "Missing id",
                    }
                )
                continue

            payroll_run_id = data.get("payroll_run_id")
            employee_id = data.get("employee_id")
            if not payroll_run_id or not employee_id:
                rejected.append(
                    {
                        "entity": "payroll_line_items",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "payroll_run_id and employee_id are required",
                    }
                )
                continue

            run = await self.session.get(PayrollRun, payroll_run_id)
            if run is None or run.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "payroll_line_items",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Payroll run not found",
                    }
                )
                continue

            if run.status == "paid":
                rejected.append(
                    {
                        "entity": "payroll_line_items",
                        "id": record_id,
                        "code": "PAYROLL_FINALIZED",
                        "message": "Payroll is finalized",
                    }
                )
                continue

            employee = await self.session.get(Employee, employee_id)
            if employee is None or employee.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "payroll_line_items",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Employee not found",
                    }
                )
                continue

            if operation == "delete":
                item = await self.session.get(PayrollLineItem, record_id)
                if item and item.organization_id == organization_id:
                    item.deleted_at = datetime.now(timezone.utc)
                    item.version += 1
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            existing_for_employee = await self.session.scalar(
                select(PayrollLineItem).where(
                    PayrollLineItem.payroll_run_id == payroll_run_id,
                    PayrollLineItem.employee_id == employee_id,
                    PayrollLineItem.deleted_at.is_(None),
                )
            )

            item = await self.session.get(PayrollLineItem, record_id)
            if item is None and existing_for_employee is not None:
                item = existing_for_employee
                record_id = existing_for_employee.id

            if item is None:
                item = PayrollLineItem(
                    id=record_id,
                    organization_id=organization_id,
                    payroll_run_id=payroll_run_id,
                    employee_id=employee_id,
                    base_salary=self._float_or_zero(data.get("base_salary")),
                    total_allowances=self._float_or_zero(data.get("total_allowances")),
                    total_deductions=self._float_or_zero(data.get("total_deductions")),
                    overtime_amount=self._float_or_zero(data.get("overtime_amount")),
                    bonus_amount=self._float_or_zero(data.get("bonus_amount")),
                    net_salary=self._float_or_zero(data.get("net_salary")),
                    days_worked=self._float_or_zero(data.get("days_worked")),
                    days_in_period=self._float_or_zero(data.get("days_in_period")),
                )
                self.session.add(item)
            elif item.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "payroll_line_items",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Line item belongs to another organization",
                    }
                )
                continue
            else:
                item.payroll_run_id = payroll_run_id
                item.employee_id = employee_id
                item.base_salary = self._float_or_zero(data.get("base_salary"))
                item.total_allowances = self._float_or_zero(data.get("total_allowances"))
                item.total_deductions = self._float_or_zero(data.get("total_deductions"))
                item.overtime_amount = self._float_or_zero(data.get("overtime_amount"))
                item.bonus_amount = self._float_or_zero(data.get("bonus_amount"))
                item.net_salary = self._float_or_zero(data.get("net_salary"))
                item.days_worked = self._float_or_zero(data.get("days_worked"))
                item.days_in_period = self._float_or_zero(data.get("days_in_period"))
                item.version += 1
                item.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                item.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_payroll_line_items(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(PayrollLineItem).where(PayrollLineItem.organization_id == organization_id)
        if since is not None:
            query = query.where(PayrollLineItem.updated_at >= since)
        result = await self.session.execute(query.order_by(PayrollLineItem.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for item in result.scalars():
            operation = "delete" if item.deleted_at else "update"
            records.append(
                {
                    "id": item.id,
                    "operation": operation,
                    "data": {
                        "id": item.id,
                        "organization_id": item.organization_id,
                        "payroll_run_id": item.payroll_run_id,
                        "employee_id": item.employee_id,
                        "base_salary": float(item.base_salary),
                        "total_allowances": float(item.total_allowances),
                        "total_deductions": float(item.total_deductions),
                        "overtime_amount": float(item.overtime_amount),
                        "bonus_amount": float(item.bonus_amount),
                        "net_salary": float(item.net_salary),
                        "days_worked": float(item.days_worked),
                        "days_in_period": float(item.days_in_period),
                        "version": item.version,
                    },
                    "version": item.version,
                    "updated_at": item.updated_at.isoformat(),
                    "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
                }
            )
        return records

    async def push_products(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "products", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                product = await self.session.get(Product, record_id)
                if product and product.organization_id == organization_id:
                    product.deleted_at = datetime.now(timezone.utc)
                    product.version += 1
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            name = data.get("name")
            if not name:
                rejected.append(
                    {
                        "entity": "products",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "name is required",
                    }
                )
                continue

            category_id = data.get("category_id")
            if category_id:
                category = await self.session.get(ProductCategory, category_id)
                if category is None or category.organization_id != organization_id:
                    category_id = None

            product = await self.session.get(Product, record_id)
            if product is None:
                product = Product(
                    id=record_id,
                    organization_id=organization_id,
                    category_id=category_id,
                    name=str(name).strip(),
                    sku=data.get("sku"),
                    unit=str(data.get("unit") or "pcs"),
                    current_stock=self._float_or_zero(data.get("current_stock")),
                    low_stock_threshold=self._float_or_zero(data.get("low_stock_threshold")),
                    cost_price=self._optional_float(data.get("cost_price")),
                    selling_price=self._optional_float(data.get("selling_price")),
                    description=data.get("description"),
                    created_by=user_id,
                )
                self.session.add(product)
            elif product.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "products",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Product belongs to another organization",
                    }
                )
                continue
            else:
                product.name = str(name).strip()
                product.category_id = category_id
                product.sku = data.get("sku")
                product.unit = str(data.get("unit") or product.unit)
                if data.get("current_stock") is not None:
                    product.current_stock = self._float_or_zero(data.get("current_stock"))
                product.low_stock_threshold = self._float_or_zero(
                    data.get("low_stock_threshold", product.low_stock_threshold)
                )
                product.cost_price = self._optional_float(data.get("cost_price"))
                product.selling_price = self._optional_float(data.get("selling_price"))
                product.description = data.get("description")
                product.version += 1
                product.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                product.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_product_categories(self, organization_id: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(ProductCategory).where(
                ProductCategory.organization_id == organization_id,
                ProductCategory.deleted_at.is_(None),
            )
        )
        records: list[dict[str, Any]] = []
        for category in result.scalars():
            records.append(
                {
                    "id": category.id,
                    "operation": "update",
                    "data": {
                        "id": category.id,
                        "organization_id": category.organization_id,
                        "name": category.name,
                        "version": category.version,
                    },
                    "version": category.version,
                    "updated_at": category.updated_at.isoformat(),
                    "deleted_at": None,
                }
            )
        return records

    async def pull_products(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(Product).where(Product.organization_id == organization_id)
        if since is not None:
            query = query.where(Product.updated_at >= since)
        result = await self.session.execute(query.order_by(Product.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for product in result.scalars():
            operation = "delete" if product.deleted_at else "update"
            records.append(
                {
                    "id": product.id,
                    "operation": operation,
                    "data": {
                        "id": product.id,
                        "organization_id": product.organization_id,
                        "category_id": product.category_id,
                        "name": product.name,
                        "sku": product.sku,
                        "unit": product.unit,
                        "current_stock": float(product.current_stock),
                        "low_stock_threshold": float(product.low_stock_threshold),
                        "cost_price": float(product.cost_price) if product.cost_price is not None else None,
                        "selling_price": float(product.selling_price) if product.selling_price is not None else None,
                        "description": product.description,
                        "version": product.version,
                    },
                    "version": product.version,
                    "updated_at": product.updated_at.isoformat(),
                    "deleted_at": product.deleted_at.isoformat() if product.deleted_at else None,
                }
            )
        return records

    async def push_stock_movements(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {
                        "entity": "stock_movements",
                        "id": None,
                        "code": "VALIDATION_ERROR",
                        "message": "Missing id",
                    }
                )
                continue

            if operation == "delete":
                movement = await self.session.get(StockMovement, record_id)
                if movement and movement.organization_id == organization_id:
                    movement.deleted_at = datetime.now(timezone.utc)
                    movement.version += 1
                    accepted.append(record_id)
                else:
                    accepted.append(record_id)
                continue

            product_id = data.get("product_id")
            movement_type = data.get("movement_type")
            quantity_raw = data.get("quantity")
            movement_date_raw = data.get("movement_date")

            if not product_id or not movement_type or quantity_raw is None or movement_date_raw is None:
                rejected.append(
                    {
                        "entity": "stock_movements",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "product_id, movement_type, quantity, and movement_date are required",
                    }
                )
                continue

            try:
                quantity = float(quantity_raw)
                if quantity <= 0:
                    raise ValueError
                movement_date = date.fromisoformat(str(movement_date_raw)[:10])
            except ValueError:
                rejected.append(
                    {
                        "entity": "stock_movements",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid quantity or movement_date",
                    }
                )
                continue

            if movement_type not in {"in", "out", "adjustment"}:
                rejected.append(
                    {
                        "entity": "stock_movements",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid movement_type",
                    }
                )
                continue

            product = await self.session.get(Product, product_id)
            if product is None or product.organization_id != organization_id or product.deleted_at is not None:
                rejected.append(
                    {
                        "entity": "stock_movements",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Product not found",
                    }
                )
                continue

            existing = await self.session.get(StockMovement, record_id)
            if existing is not None:
                accepted.append(record_id)
                continue

            if movement_type == "out" and float(product.current_stock) < quantity:
                rejected.append(
                    {
                        "entity": "stock_movements",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "Insufficient stock",
                    }
                )
                continue

            movement = StockMovement(
                id=record_id,
                organization_id=organization_id,
                product_id=product_id,
                movement_type=movement_type,
                quantity=quantity,
                movement_date=movement_date,
                notes=data.get("notes"),
                created_by=user_id,
            )
            self.session.add(movement)

            if movement_type == "in":
                product.current_stock = float(product.current_stock) + quantity
            elif movement_type == "out":
                product.current_stock = float(product.current_stock) - quantity
            else:
                product.current_stock = quantity

            product.version += 1
            product.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                movement.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_stock_movements(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(StockMovement).where(StockMovement.organization_id == organization_id)
        if since is not None:
            query = query.where(StockMovement.updated_at >= since)
        result = await self.session.execute(query.order_by(StockMovement.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for movement in result.scalars():
            operation = "delete" if movement.deleted_at else "update"
            records.append(
                {
                    "id": movement.id,
                    "operation": operation,
                    "data": {
                        "id": movement.id,
                        "organization_id": movement.organization_id,
                        "product_id": movement.product_id,
                        "movement_type": movement.movement_type,
                        "quantity": float(movement.quantity),
                        "movement_date": movement.movement_date.isoformat(),
                        "notes": movement.notes,
                        "version": movement.version,
                    },
                    "version": movement.version,
                    "updated_at": movement.updated_at.isoformat(),
                    "deleted_at": movement.deleted_at.isoformat() if movement.deleted_at else None,
                }
            )
        return records

    async def push_customers(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "customers", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                customer = await self.session.get(Customer, record_id)
                if customer and customer.organization_id == organization_id:
                    customer.deleted_at = datetime.now(timezone.utc)
                    customer.version += 1
                accepted.append(record_id)
                continue

            name = data.get("name")
            if not name:
                rejected.append(
                    {
                        "entity": "customers",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "name is required",
                    }
                )
                continue

            customer = await self.session.get(Customer, record_id)
            if customer is None:
                customer = Customer(
                    id=record_id,
                    organization_id=organization_id,
                    name=str(name).strip(),
                    phone=data.get("phone"),
                    email=data.get("email"),
                    address=data.get("address"),
                    gstin=data.get("gstin"),
                    notes=data.get("notes"),
                    created_by=user_id,
                )
                self.session.add(customer)
            elif customer.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "customers",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Customer belongs to another organization",
                    }
                )
                continue
            else:
                customer.name = str(name).strip()
                customer.phone = data.get("phone")
                customer.email = data.get("email")
                customer.address = data.get("address")
                customer.gstin = data.get("gstin")
                customer.notes = data.get("notes")
                customer.version += 1
                customer.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                customer.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_customers(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(Customer).where(Customer.organization_id == organization_id)
        if since is not None:
            query = query.where(Customer.updated_at >= since)
        result = await self.session.execute(query.order_by(Customer.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for customer in result.scalars():
            operation = "delete" if customer.deleted_at else "update"
            records.append(
                {
                    "id": customer.id,
                    "operation": operation,
                    "data": {
                        "id": customer.id,
                        "organization_id": customer.organization_id,
                        "name": customer.name,
                        "phone": customer.phone,
                        "email": customer.email,
                        "address": customer.address,
                        "gstin": customer.gstin,
                        "outstanding_balance": float(customer.outstanding_balance),
                        "notes": customer.notes,
                        "version": customer.version,
                    },
                    "version": customer.version,
                    "updated_at": customer.updated_at.isoformat(),
                    "deleted_at": customer.deleted_at.isoformat() if customer.deleted_at else None,
                }
            )
        return records

    async def push_vendors(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "vendors", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                vendor = await self.session.get(Vendor, record_id)
                if vendor and vendor.organization_id == organization_id:
                    vendor.deleted_at = datetime.now(timezone.utc)
                    vendor.version += 1
                accepted.append(record_id)
                continue

            name = data.get("name")
            if not name:
                rejected.append(
                    {
                        "entity": "vendors",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "name is required",
                    }
                )
                continue

            vendor = await self.session.get(Vendor, record_id)
            if vendor is None:
                vendor = Vendor(
                    id=record_id,
                    organization_id=organization_id,
                    name=str(name).strip(),
                    phone=data.get("phone"),
                    email=data.get("email"),
                    address=data.get("address"),
                    gstin=data.get("gstin"),
                    notes=data.get("notes"),
                    created_by=user_id,
                )
                self.session.add(vendor)
            elif vendor.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "vendors",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Vendor belongs to another organization",
                    }
                )
                continue
            else:
                vendor.name = str(name).strip()
                vendor.phone = data.get("phone")
                vendor.email = data.get("email")
                vendor.address = data.get("address")
                vendor.gstin = data.get("gstin")
                vendor.notes = data.get("notes")
                vendor.version += 1
                vendor.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                vendor.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_vendors(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(Vendor).where(Vendor.organization_id == organization_id)
        if since is not None:
            query = query.where(Vendor.updated_at >= since)
        result = await self.session.execute(query.order_by(Vendor.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for vendor in result.scalars():
            operation = "delete" if vendor.deleted_at else "update"
            records.append(
                {
                    "id": vendor.id,
                    "operation": operation,
                    "data": {
                        "id": vendor.id,
                        "organization_id": vendor.organization_id,
                        "name": vendor.name,
                        "phone": vendor.phone,
                        "email": vendor.email,
                        "address": vendor.address,
                        "gstin": vendor.gstin,
                        "outstanding_balance": float(vendor.outstanding_balance),
                        "notes": vendor.notes,
                        "version": vendor.version,
                    },
                    "version": vendor.version,
                    "updated_at": vendor.updated_at.isoformat(),
                    "deleted_at": vendor.deleted_at.isoformat() if vendor.deleted_at else None,
                }
            )
        return records

    async def push_vehicles(
        self, organization_id: str, user_id: str, changes: list[dict[str, Any]]
    ) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for change in changes:
            operation = change.get("operation")
            data = change.get("data") or {}
            record_id = change.get("id")
            if not record_id:
                rejected.append(
                    {"entity": "vehicles", "id": None, "code": "VALIDATION_ERROR", "message": "Missing id"}
                )
                continue

            if operation == "delete":
                vehicle = await self.session.get(Vehicle, record_id)
                if vehicle and vehicle.organization_id == organization_id:
                    vehicle.deleted_at = datetime.now(timezone.utc)
                    vehicle.version += 1
                accepted.append(record_id)
                continue

            name = data.get("name")
            if not name:
                rejected.append(
                    {
                        "entity": "vehicles",
                        "id": record_id,
                        "code": "VALIDATION_ERROR",
                        "message": "name is required",
                    }
                )
                continue

            driver_employee_id = data.get("driver_employee_id")
            if driver_employee_id:
                driver = await self.session.get(Employee, driver_employee_id)
                if driver is None or driver.organization_id != organization_id:
                    driver_employee_id = None

            vehicle = await self.session.get(Vehicle, record_id)
            if vehicle is None:
                vehicle = Vehicle(
                    id=record_id,
                    organization_id=organization_id,
                    name=str(name).strip(),
                    registration_number=data.get("registration_number"),
                    driver_employee_id=driver_employee_id,
                    loading_charge_per_unit=self._float_or_zero(data.get("loading_charge_per_unit")),
                    unloading_charge_per_unit=self._float_or_zero(data.get("unloading_charge_per_unit")),
                    default_labour_employee_ids=data.get("default_labour_employee_ids"),
                    notes=data.get("notes"),
                    is_active=bool(data.get("is_active", True)),
                    created_by=user_id,
                )
                self.session.add(vehicle)
            elif vehicle.organization_id != organization_id:
                rejected.append(
                    {
                        "entity": "vehicles",
                        "id": record_id,
                        "code": "PERMISSION_DENIED",
                        "message": "Vehicle belongs to another organization",
                    }
                )
                continue
            else:
                vehicle.name = str(name).strip()
                vehicle.registration_number = data.get("registration_number")
                vehicle.driver_employee_id = driver_employee_id
                vehicle.loading_charge_per_unit = self._float_or_zero(data.get("loading_charge_per_unit"))
                vehicle.unloading_charge_per_unit = self._float_or_zero(data.get("unloading_charge_per_unit"))
                vehicle.default_labour_employee_ids = data.get("default_labour_employee_ids")
                vehicle.notes = data.get("notes")
                vehicle.is_active = bool(data.get("is_active", True))
                vehicle.version += 1
                vehicle.updated_at = datetime.now(timezone.utc)

            client_updated_at = change.get("client_updated_at")
            if client_updated_at:
                vehicle.client_updated_at = datetime.fromisoformat(str(client_updated_at).replace("Z", "+00:00"))

            accepted.append(record_id)

        await self.session.commit()
        return accepted, rejected, conflicts

    async def pull_vehicles(self, organization_id: str, since: datetime | None) -> list[dict[str, Any]]:
        query = select(Vehicle).where(Vehicle.organization_id == organization_id)
        if since is not None:
            query = query.where(Vehicle.updated_at >= since)
        result = await self.session.execute(query.order_by(Vehicle.updated_at.asc()))
        records: list[dict[str, Any]] = []
        for vehicle in result.scalars():
            operation = "delete" if vehicle.deleted_at else "update"
            records.append(
                {
                    "id": vehicle.id,
                    "operation": operation,
                    "data": {
                        "id": vehicle.id,
                        "organization_id": vehicle.organization_id,
                        "name": vehicle.name,
                        "registration_number": vehicle.registration_number,
                        "driver_employee_id": vehicle.driver_employee_id,
                        "loading_charge_per_unit": float(vehicle.loading_charge_per_unit),
                        "unloading_charge_per_unit": float(vehicle.unloading_charge_per_unit),
                        "default_labour_employee_ids": vehicle.default_labour_employee_ids,
                        "notes": vehicle.notes,
                        "is_active": vehicle.is_active,
                        "version": vehicle.version,
                    },
                    "version": vehicle.version,
                    "updated_at": vehicle.updated_at.isoformat(),
                    "deleted_at": vehicle.deleted_at.isoformat() if vehicle.deleted_at else None,
                }
            )
        return records

    async def _refresh_customer_balance(self, customer_id: str) -> None:
        total = await self.session.scalar(
            select(func.coalesce(func.sum(RevenueEntry.amount), 0)).where(
                RevenueEntry.customer_id == customer_id,
                RevenueEntry.deleted_at.is_(None),
            )
        )
        customer = await self.session.get(Customer, customer_id)
        if customer is not None:
            customer.outstanding_balance = float(total or 0)
            customer.version += 1
            customer.updated_at = datetime.now(timezone.utc)

    async def _refresh_vendor_balance(self, vendor_id: str) -> None:
        total = await self.session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.vendor_id == vendor_id,
                Expense.deleted_at.is_(None),
            )
        )
        vendor = await self.session.get(Vendor, vendor_id)
        if vendor is not None:
            vendor.outstanding_balance = float(total or 0)
            vendor.version += 1
            vendor.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _int_or_zero(value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float_or_zero(value: Any) -> float:
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_optional_datetime(value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
