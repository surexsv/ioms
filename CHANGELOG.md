# Changelog

## [1.0.0] — 2026-06-04 — Version 1 (baseline)

### Infomates Operations Management System (IOMS)

First stable release. Use tag `v1.0.0` in Git or archive `releases/IOMS-v1.0.0.zip`.

### Platform
- Django 6 field-service OMS with role-based access
- Corporate ERP UI (navy `#0F2D52`, Segoe UI, `static/css/ioms.css`)
- Left sidebar: logo, **IOMS** label, full navigation, user footer
- Top center header: **Infomates Operations Management System** (center-aligned)

### Modules
- Accounts, Clients, Orders, WCR, BOQ, Billing (PDF invoices)
- Attendance (check-in/out, reports)
- Quotations (rate cards, workflow, PDF, convert to order)
- Director / Engineer / Supervisor dashboards with Chart.js

### Branding
- `static/branding/infomates_logo.png`
- `config/company.py`

### Commands
- `python manage.py setup_demo`
- `python manage.py seed_rate_cards`
- `python manage.py runserver`
