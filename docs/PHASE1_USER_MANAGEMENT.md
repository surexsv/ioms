# Phase 1 — Enterprise User Management Implementation Notes

**Status:** Complete — awaiting review before Phase 2  
**Date:** 2026-07-10  
**Scope:** Database, Models, Admin, Forms, Migration only  

---

## What Was Built

### 1. Department Master
- Model: `accounts.Department`
- Admin CRUD: Django Admin → Departments
- **8 default departments** seeded on migration

### 2. Designation Master
- Model: `accounts.Designation`
- Admin CRUD: Django Admin → Designations
- **13 default designations** seeded on migration

### 3. Branch Master
- Model: `accounts.Branch`
- Admin CRUD: Django Admin → Branches
- Default: **Head Office (HO)**

### 4. Permission Master
- Model: `accounts.ModulePermission`
- **26 module permissions** seeded (individual grants per employee)
- Categories: operations, finance, procurement, hr, management, administration
- Superuser-only permissions: `user_management`, `role_management`, `settings`, `system_configuration`, `database_configuration`

### 5. Employee Master
- Model: `accounts.Employee` (OneToOne → `User`)
- Fields: employee_code, department, designation, reporting_manager, branch, employment_type, mobile, joining_date, status
- Employee name & email come from linked `User`
- Permissions via `EmployeePermissionGrant` (M2M through table)

### 6. Individual Permission Grants
- Model: `accounts.EmployeePermissionGrant`
- **Not linked to designation** — assigned per employee in admin
- Inline editor on Employee admin + standalone grant admin

---

## Files Created / Modified

| File | Action |
|------|--------|
| `accounts/enterprise_constants.py` | **Created** — defaults, legacy mapping |
| `accounts/enterprise_models.py` | **Created** — Department, Designation, Branch, ModulePermission, Employee, EmployeePermissionGrant |
| `accounts/enterprise_migration.py` | **Created** — seed + user migration helpers |
| `accounts/employee_forms.py` | **Created** — ModelForms for all masters |
| `accounts/migrations/0009_enterprise_user_management_phase1.py` | **Created** — schema + data migration |
| `accounts/admin.py` | **Modified** — full CRUD for all new models |
| `accounts/models.py` | **Modified** — import enterprise models |
| `accounts/management/commands/seed_enterprise_masters.py` | **Created** — re-seed command |

### NOT Modified (Phase 2 scope)
- `accounts/permissions.py` — legacy `_ACCESS` still active
- `accounts/middleware.py` — still uses legacy `can_access()`
- `accounts/context_processors.py` — hardcoded nav flags
- `templates/base.html` — hardcoded menu
- Registration forms — still use deprecated `role_requested` (unchanged for compatibility)
- Dashboard widgets — unchanged

---

## Migration Details

**Migration:** `accounts.0009_enterprise_user_management_phase1`

### Step 1 — Schema
Creates: Branch, Department, Designation, ModulePermission, Employee, EmployeePermissionGrant

### Step 2 — Seed Masters
Populates default departments, designations, Head Office branch, 26 permissions

### Step 3 — Migrate Existing Users
For each `User`:
1. Creates `Employee` profile if missing
2. Maps `role` → Department + Designation via `LEGACY_ROLE_ORG_MAP`
3. Falls back to text `department`/`designation` fields if possible
4. Copies `reports_to` → `reporting_manager`
5. Sets `employee_code` from `employee_id` or `EMP{pk}`
6. Grants permissions from legacy `_ACCESS` matrix → new `ModulePermission` codenames
7. **Superusers** receive all permissions including admin-only
8. **Non-superuser Directors** receive operational permissions only (no user_management, settings, etc.)

### Rollback
Reverse migration deletes Employee grants and Employee records (masters remain).

---

## Legacy Role → Permission Mapping (Automatic)

| Legacy Role | Default Department | Default Designation |
|-------------|-------------------|---------------------|
| DIRECTOR | Management | Director |
| OPERATIONS | Operations | Operations Manager |
| PROJECT_MANAGER | Projects | Project Manager |
| SUPERVISOR | Operations | Team Leader |
| ACCOUNTS | Accounts | Accounts Manager |
| ACCOUNTS_EXECUTIVE | Accounts | Accounts Executive |
| BACK_OFFICE | HR & Administration | HR & Admin Executive |
| ENGINEER | Operations | Engineer |
| Technician | Operations | Technician |

---

## How to Verify Phase 1

```bash
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py check
```

### Django Admin checks
1. Login as superuser → `/admin/`
2. Verify **Departments** (8 records)
3. Verify **Designations** (13 records)
4. Verify **Branches** (Head Office)
5. Verify **Module Permissions** (26 records)
6. Open **Employees** — every existing user should have a profile
7. Open an Employee → verify **Permission grants** inline
8. Open **Users** → see **Employee Profile** inline

### Re-sync command (if needed)
```bash
venv\Scripts\python.exe manage.py seed_enterprise_masters
venv\Scripts\python.exe manage.py seed_enterprise_masters --sync-employees
```

---

## Backward Compatibility

| Area | Status |
|------|--------|
| Existing users | ✅ Employee profile auto-created |
| Login / auth | ✅ Unchanged |
| `User.role` field | ✅ Retained (marked legacy in admin) |
| `role_requested` | ✅ Retained on registration (deprecated label) |
| Orders, WCR, Billing | ✅ Unchanged — still use legacy permissions |
| Navigation | ✅ Unchanged — still hardcoded |
| Access control | ✅ Unchanged — still uses `_ACCESS` / `can_access()` |

**Important:** `Employee.has_permission()` exists but is **not wired** to views yet. Phase 2 will switch enforcement.

---

## Phase 2 Preview (NOT started — awaiting approval)

1. Replace `can_access()` with `employee.has_permission(codename)`
2. Permission-driven navigation from `ModulePermission.menu_url_name`
3. Permission-based dashboard widgets
4. Update registration to use Department/Designation dropdowns (remove role_requested)
5. GPS visibility gated on `gps_tracking` permission
6. Approval workflow uses `reporting_manager` hierarchy

---

## Phase 3 Preview (NOT started)

1. Remove legacy `User.role` and `role_requested`
2. Remove `_ACCESS` static matrix
3. Full migration verification test suite
4. Update `ROLE_PERMISSION_MATRIX.json` to new model

---

## Review Checklist

- [ ] All departments/designations match your organization?
- [ ] Permission list complete (26 modules)?
- [ ] Existing users migrated with correct permissions?
- [ ] Superuser vs Director permission split acceptable?
- [ ] Employee admin UX sufficient for HR team?
- [ ] Approve Phase 2 start?

**STOP — Awaiting your review before Phase 2.**
