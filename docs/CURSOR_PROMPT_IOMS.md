# Cursor Prompt — Infomates Operations Management System (IOMS)

Copy everything below the line into a **new Cursor chat** when continuing work on this project.

---

## Project context

You are working on **Infomates Operations Management System (IOMS)** — a Django 6 field-service / ERP-style web application.

**Workspace:** `E:\Infomates_Development\infomates_oms`  
**Version baseline:** **1.0.0** (see `VERSION`, `docs/VERSION_1_RELEASE.md`)

**Stack:** Django 6, SQLite, server-rendered templates, ReportLab PDFs, Chart.js on director dashboard, Bootstrap Icons.

**Run:**
```bash
venv\Scripts\python.exe manage.py runserver
venv\Scripts\python.exe manage.py setup_demo
venv\Scripts\python.exe manage.py seed_rate_cards
```

**Demo login:** `admin` / `admin123` (Director)

---

## Design system (do not break)

| Token | Value |
|-------|--------|
| Primary navy | `#0F2D52` |
| Secondary blue | `#2C5282` |
| Hover | `#1F4E79` |
| Active nav | `#2C5282` |
| Page background | `#F4F6F9` |
| Font | Segoe UI, Roboto fallbacks |

**CSS:** `static/css/ioms.css`  
**Base layout:** `templates/base.html`

### Layout rules (Version 1+)

1. **Left sidebar (fixed on desktop)**
   - Company logo only (white panel behind logo on navy sidebar)
   - Label under logo: **`IOMS`** (not “Operations Management”)
   - Full navigation menu below logo (role-based links)
   - User name, role, logout at bottom

2. **Top center header (main content column)**
   - Centered title: **`Infomates Operations Management System`**
   - Dark navy background, white text, sticky
   - **No logo** in this header (logo stays sidebar only)
   - Mobile: hamburger opens sidebar; shortened title if needed

3. **Do not** duplicate the navigation menu in the top header unless explicitly requested.

4. **Dashboard content** starts below the header (KPI cards, charts, tables).

---

## Apps and URLs

| App | Path prefix |
|-----|-------------|
| accounts | `/`, `/login/` |
| dashboard | `/dashboard/` |
| orders | `/orders/` |
| clients | `/clients/` |
| quotations | `/quotations/` |
| wcr | `/wcr/` |
| boq | `/boq/` |
| billing | `/billing/` |
| attendance | `/attendance/` |

**Settings:** `config/settings.py`, `config/urls.py`, `config/company.py`

---

## Roles and permissions (summary)

| Role | Typical access |
|------|----------------|
| DIRECTOR | Full |
| OPERATIONS | Orders, quotations create/approve, BOQ, etc. |
| ACCOUNTS | Billing, rate cards, view quotations |
| ENGINEER / Technician | My orders, my attendance, view quotations (read-only) |
| Supervisor | Team orders, WCR, BOQ, billing, attendance |

Decorators: `accounts/decorators.py` (`role_required`)  
Nav context: `accounts/context_processors.py`

---

## Quotation module (v1)

- Models: `quotations/models.py` — Quotation, ServiceRateCard, MaterialRateCard, line items, RateCardAuditLog
- Workflow: Draft → Under Review → Approved → Sent → Accepted/Rejected → Converted To Order
- PDF: `quotations/pdf.py` (same branding as invoices)
- Convert: `quotations/services.py` → creates `orders.Order`, links `quotation.converted_order`

---

## Coding standards

- Match existing patterns in neighboring apps (BOQ, billing).
- Minimize scope; do not refactor unrelated code.
- Do not change URLs or break existing views without migration plan.
- Git commits **only when the user asks**.
- Use `{% load static %}` for assets; logo at `static/branding/infomates_logo.png`.

---

## Common tasks (examples)

**Add a field to quotations:** model → migration → form → template → PDF if needed.

**New sidebar link:** `templates/base.html` + `accounts/context_processors.py` (`_active_nav`) + `urls.py`.

**Dashboard widget:** `dashboard/views.py` + `templates/dashboard/dashboard.html`.

---

## Verification checklist

After UI changes:

- [ ] Sidebar shows logo + **IOMS** + menu
- [ ] Top header shows full **Infomates Operations Management System**
- [ ] Logo not duplicated in center header
- [ ] Mobile sidebar toggle works
- [ ] `python manage.py check` passes
- [ ] Director dashboard loads charts
- [ ] Quotations list/create/PDF/convert still work

---

## Optional follow-up tasks (user may request)

- Export quotation Excel
- Email quotation PDF to client
- Quotation revision history
- Dark/light theme toggle

---

*End of Cursor prompt — baseline Version 1.0.0*
