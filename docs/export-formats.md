# SmartOps Export Formats

> Related docs: [MVP Requirements — Data Export](./mvp-requirements.md#data-export) · [Database Design](./database-design.md) · [UI/UX Screens — Shared Dialogs](./ui-ux-screens.md#shared-dialogs-and-sheets)

## Overview

Export specifications for SmartOps MVP data exports: CSV files for expenses, revenue, and attendance; PDF payslips in English and Hindi.

| Export | Format | MVP tier | RBAC |
|---|---|---|---|
| Expenses list | CSV | All users (Starter+ gated post-billing) | Owner, Manager |
| Revenue list | CSV | All users | Owner, Manager |
| Attendance report | CSV | Starter+ (post-billing) | Owner, Manager |
| Payslip | PDF (EN/HI) | Starter+ (post-billing) | Owner, Manager (all); Employee (own only) |

**MVP note:** Billing not active in v1.0 — all exports available to all beta users. Tier gating enforced in Phase 1.5.

---

## CSV Conventions (All Exports)

| Rule | Detail |
|---|---|
| Encoding | UTF-8 with BOM (Excel compatibility on Windows) |
| Delimiter | Comma (`,`) |
| Quote character | Double quote (`"`) — escape internal quotes as `""` |
| Date format | `YYYY-MM-DD` (ISO 8601) |
| DateTime format | `YYYY-MM-DD HH:MM:SS` (24-hour, org timezone) |
| Currency | Plain decimal, no ₹ symbol (e.g. `1200.50`) — currency in header or filename |
| Filename pattern | `{entity}_{org_name}_{from_date}_{to_date}.csv` |
| Empty fields | Empty string, not `NULL` |
| Header row | Always first row; English column names regardless of UI locale |

**Export trigger:** Settings or list screen → Export → date range picker → confirm dialog (D-005 in [UI/UX Screens](./ui-ux-screens.md)).

---

## Expenses CSV

### Columns

| # | Column | Type | Source | Example |
|---|---|---|---|---|
| 1 | `id` | UUID | expenses.id | `550e8400-e29b-41d4-a716-446655440000` |
| 2 | `expense_date` | DATE | expenses.expense_date | `2026-06-05` |
| 3 | `category` | string | expense_categories.name | `Utilities` |
| 4 | `amount` | decimal | expenses.amount | `1200.50` |
| 5 | `currency` | string | expenses.currency_code | `INR` |
| 6 | `description` | string | expenses.description | `Electricity bill June` |
| 7 | `payment_method` | string | expenses.payment_method | `cash` |
| 8 | `vendor` | string | vendors.full_name | `Rajesh Electricals` |
| 9 | `reference_number` | string | expenses.reference_number | `INV-2026-001` |
| 10 | `has_attachment` | boolean | expenses.attachment_key != null | `true` |
| 11 | `created_at` | datetime | expenses.created_at | `2026-06-05 09:30:00` |
| 12 | `created_by` | string | users display name | `Rajesh Sharma` |

### Sample

```csv
id,expense_date,category,amount,currency,description,payment_method,vendor,reference_number,has_attachment,created_at,created_by
550e8400-e29b-41d4-a716-446655440000,2026-06-05,Utilities,1200.50,INR,Electricity bill June,cash,Rajesh Electricals,INV-2026-001,true,2026-06-05 09:30:00,Rajesh Sharma
```

### Filters

- Date range: required (from list filter or export dialog)
- Category: optional
- Payment method: optional

---

## Revenue CSV

### Columns

| # | Column | Type | Source | Example |
|---|---|---|---|---|
| 1 | `id` | UUID | revenue_entries.id | |
| 2 | `revenue_date` | DATE | revenue_entries.revenue_date | `2026-06-05` |
| 3 | `category` | string | revenue_categories.name | `Product Sales` |
| 4 | `amount` | decimal | revenue_entries.amount | `5000.00` |
| 5 | `currency` | string | revenue_entries.currency_code | `INR` |
| 6 | `description` | string | revenue_entries.description | `Daily sales` |
| 7 | `payment_method` | string | revenue_entries.payment_method | `upi` |
| 8 | `customer` | string | customers.full_name | `Suresh Traders` |
| 9 | `reference_number` | string | revenue_entries.reference_number | `TXN123456` |
| 10 | `created_at` | datetime | revenue_entries.created_at | |
| 11 | `created_by` | string | users display name | |

### Sample

```csv
id,revenue_date,category,amount,currency,description,payment_method,customer,reference_number,created_at,created_by
660e8400-e29b-41d4-a716-446655440001,2026-06-05,Product Sales,5000.00,INR,Daily sales,upi,Suresh Traders,TXN123456,2026-06-05 18:00:00,Rajesh Sharma
```

---

## Attendance Report CSV

### Columns

| # | Column | Type | Source | Example |
|---|---|---|---|---|
| 1 | `employee_code` | string | employees.employee_code | `EMP001` |
| 2 | `employee_name` | string | employees.full_name | `Ramesh Kumar` |
| 3 | `department` | string | departments.name | `Sales` |
| 4 | `attendance_date` | DATE | attendance_records.attendance_date | `2026-06-05` |
| 5 | `status` | string | attendance_records.status | `present` |
| 6 | `check_in` | time | attendance_records.check_in_time | `09:15:00` |
| 7 | `check_out` | time | attendance_records.check_out_time | `18:00:00` |
| 8 | `notes` | string | attendance_records.notes | |

### Summary row (optional footer)

After detail rows, append summary section:

```csv

SUMMARY
employee_name,days_present,days_absent,days_leave,days_half_day
Ramesh Kumar,22,2,1,0
```

### Filters

- Month or custom date range: required
- Department: optional
- Employee: optional (single employee report)

---

## Payslip PDF

Generated on payroll finalize (`status: processed` or `paid`). Stored in R2; key saved to `payroll_line_items.payslip_file_key`. Available offline after first download.

### Page layout

Single A4 page per employee per payroll run.

```
┌─────────────────────────────────────────────┐
│  [Org Logo]          PAYSLIP                 │
│  {organization_name}                         │
│  {organization_address}                      │
├─────────────────────────────────────────────┤
│  Employee: {full_name}     Code: {emp_code}  │
│  Department: {dept}        Designation: {des}│
│  Pay Period: {period_start} – {period_end}   │
├─────────────────────────────────────────────┤
│  EARNINGS                    AMOUNT (₹)      │
│  Base Salary                 {base_salary}   │
│  HRA                         {hra}           │
│  Transport Allowance         {transport}     │
│  Other Allowances            {other_allow}   │
│  Overtime                    {overtime}      │
│  Bonus                       {bonus}         │
│  ─────────────────────────────────────────   │
│  Gross Earnings              {gross}         │
├─────────────────────────────────────────────┤
│  DEDUCTIONS                  AMOUNT (₹)      │
│  PF                          {pf}            │
│  ESI                         {esi}           │
│  Tax (TDS)                   {tax}           │
│  Other Deductions            {other_ded}     │
│  ─────────────────────────────────────────   │
│  Total Deductions            {total_ded}     │
├─────────────────────────────────────────────┤
│  ATTENDANCE                                  │
│  Days Worked: {days_worked}  Absent: {absent}│
├─────────────────────────────────────────────┤
│  NET PAY                     ₹ {net_salary}  │
│                          (in words: {words}) │
├─────────────────────────────────────────────┤
│  Generated: {date}    This is a computer-    │
│  generated payslip.   generated document.    │
└─────────────────────────────────────────────┘
```

### Localization

| Element | English | Hindi |
|---|---|---|
| Title | PAYSLIP | वेतन पर्ची |
| Earnings header | EARNINGS | आय |
| Deductions header | DEDUCTIONS | कटौती |
| Net pay label | NET PAY | शुद्ध वेतन |
| Days worked | Days Worked | कार्य दिवस |
| Amount in words | Rupees {words} only | रुपये {words} मात्र |

- Use org default language from `organization_settings.default_language`
- Employee can override with personal language preference for own payslip view
- Numbers formatted per locale (`en_IN` / `hi_IN`) via `intl`
- Font: Noto Sans Devanagari for Hindi sections; Roboto for English

### Amount in words

Convert net salary to Indian numbering words (lakhs/crores):

| Net salary | English words |
|---|---|
| ₹14,500.00 | Rupees Fourteen Thousand Five Hundred only |
| ₹1,25,000.00 | Rupees One Lakh Twenty Five Thousand only |

Implement via backend template engine or client-side library; must match PDF locale.

### File naming

```
payslip_{employee_code}_{period_start}_{period_end}_{locale}.pdf
```

Example: `payslip_EMP001_2026-06-01_2026-06-30_hi.pdf`

### Share action

Mobile uses system share sheet (WhatsApp, email, save to files). PDF cached locally in app documents directory after first view.

---

## Export Confirmation Dialog

Before export (D-005 pattern):

| Field | Value |
|---|---|
| Title | Export {type}? |
| Body | Export {count} records for {date range}? |
| Actions | Cancel · Export |

On success: snackbar "Export saved" + open share sheet (mobile) or download (future web).

On offline: CSV export from local Isar data allowed; payslip PDF requires prior download or blocks with "Connect to download payslip".

---

## Related Documents

- [MVP Requirements](./mvp-requirements.md) — export user stories and tier gating
- [Database Design](./database-design.md) — source table columns
- [Revenue Model](./revenue-model.md) — Starter+ feature gating (Phase 1.5)
- [Architecture — File Storage](./architecture.md#file-storage-architecture) — payslip PDF in R2
