# Infomates OMS — Version 1.0.0

**Release label:** `v1.0.0`  
**Date:** 4 June 2026  
**Product:** Infomates Operations Management System (IOMS)  
**Status:** Version 1 — frozen baseline for future work

This document marks the official **Version 1** snapshot of the Django application at  
`E:\Infomates_Development\infomates_oms`.

## Save Version 1 on your PC (one command)

```powershell
cd E:\Infomates_Development\infomates_oms
powershell -ExecutionPolicy Bypass -File scripts\save_version_1.ps1
```

This script will:
1. **Git commit** all changes (if Git is installed)
2. Create annotated tag **`v1.0.0`**
3. Create backup zip: **`releases/IOMS-v1.0.0.zip`** (excludes `venv` and `.git`)

### Manual Git (alternative)

```bash
cd E:\Infomates_Development\infomates_oms
git add -A
git commit -m "Release IOMS v1.0.0 — full OMS with quotations and finalized UI shell"
git tag -a v1.0.0 -m "IOMS Version 1.0.0 baseline"
```

### Version marker files

| File | Purpose |
|------|---------|
| `VERSION` | `1.0.0` |
| `RELEASE_v1.0.0.json` | Machine-readable release metadata |
| `CHANGELOG.md` | Release notes |
| `docs/VERSION_1_RELEASE.md` | This document |
| `docs/CURSOR_PROMPT_IOMS.md` | Cursor AI continuation prompt |

## Version 1 feature set

### Core platform
- Django 6, SQLite, custom `accounts.User` with roles
- Login/logout, role-based dashboards and routing
- Corporate UI: navy theme (`#0F2D52`), `static/css/ioms.css`, Bootstrap Icons
- Left sidebar: company logo, **IOMS** label, navigation menu, user footer
- Top center header: **Infomates Operations Management System**

### Modules
| Module | Purpose |
|--------|---------|
| `accounts` | Auth, roles (Director, Operations, Accounts, Engineer, Technician, Supervisor) |
| `clients` | Client master |
| `orders` | Orders, status workflow, role-based lists |
| `wcr` | Work completion reports |
| `boq` | Bill of quantities |
| `billing` | Invoices, PDF (ReportLab), line items |
| `attendance` | Check-in/out, reports, dashboard |
| `quotations` | Quotations, service/material rate cards, PDF, convert to order |
| `dashboard` | Director KPIs, charts, engineer/supervisor views |

### Branding
- Logo: `static/branding/infomates_logo.png`
- Company config: `config/company.py`

### Demo users (`python manage.py setup_demo`)
- `admin` / `admin123` (Director)
- `engineer1` / `engineer123`
- `supervisor1` / `supervisor123`

### Run
```bash
venv\Scripts\python.exe manage.py runserver
```

### Quotation setup
```bash
venv\Scripts\python.exe manage.py seed_rate_cards
```

## UI layout (v1.0+)

1. **Sidebar (left):** Logo → **IOMS** → menu (Dashboard, Orders, Clients, Quotations, WCR, BOQ, Billing, Attendance) → user/logout  
2. **Top header (center, main area):** Full title *Infomates Operations Management System* — **center-aligned** in the navy bar (no logo duplicate)  
3. **Content:** Page-specific KPIs, tables, forms

## Files defining the shell

- `templates/base.html`
- `static/css/ioms.css`
- `accounts/context_processors.py`

---

*Preserve this file when branching new features; compare changes against v1.0.0.*
