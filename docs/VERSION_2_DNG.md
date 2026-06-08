# IOMS Version 2.0 — Document Number Generator (DNG)

## Release baseline

- **Version 1.0.0 backup:** `releases/IOMS-v1.0.0.zip` (created before DNG implementation)
- **Version 2.0.0:** Centralized Document Number Generator

## Number format

`{CompanyPrefix}{DocPrefix}{YearSeries}{Serial}`

Example: `ITSPLORD26270001`

- Company prefix: `ITSPL` (configurable)
- Year series: rolling format — calendar 2026 → `2627`, 2027 → `2728`
- Serial: 4 digits, auto-increment per document type per year series

## Document types

| Type | Prefix | Example |
|------|--------|---------|
| Order | ORD | ITSPLORD26270001 |
| Quotation | QT | ITSPLQT26270001 |
| WCR | WCR | ITSPLWCR26270001 |
| BOQ | BOQ | ITSPLBOQ26270001 |
| Invoice | INV | ITSPLINV26270001 |
| Purchase Order | PO | ITSPLPO26270001 |

## Invoice backward compatibility

- Existing invoice numbers (e.g. `ITSPL26270001`) are **never modified**
- New invoices default to **Auto Generate** (`ITSPLINV26270001`)
- **Manual Entry** supports legacy and customer-specific numbers with uniqueness validation

## Admin access

Document Number Control Panel and Settings: **Director** and **Superuser** only.

URLs:
- `/document-generator/` — Control Panel
- `/document-generator/settings/` — Prefix & serial settings

## Post-deploy commands

```powershell
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py seed_document_counters
```

## Rollback procedure

1. Stop the application server
2. Restore database from pre-v2 backup (or restore `releases/IOMS-v1.0.0.zip` project files)
3. If using git: `git checkout v1.0.0`
4. Run `manage.py migrate` on the v1 schema if needed
5. Restart server

Existing document numbers in the database are unchanged by DNG; rollback only affects **new** numbering behaviour.
