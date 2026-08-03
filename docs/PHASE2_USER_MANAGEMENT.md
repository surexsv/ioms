# Phase 2 — Enterprise User Management Integration

**Status:** Complete — awaiting review before Phase 3  
**Date:** 2026-07-10  
**Scope:** Wire individual Employee permissions into access control, navigation, dashboards, and registration  

---

## What Was Built

### 1. Enterprise Permission Service
- **File:** `accounts/enterprise_permissions.py`
- `get_user_permission_codenames(user)` — cached permission lookup (5 min TTL)
- `has_enterprise_permission(user, codename)` — single permission check
- `can_access_via_enterprise(user, module_key)` — primary access bridge with legacy fallback
- `allowed_dashboard_for_user(user)` — permission-based dashboard routing
- `dashboard_widget_flags(user)` — dashboard section visibility
- `build_navigation_menu(user)` — permission-driven sidebar sections
- `get_reporting_manager(user)` — approval hierarchy from Employee profile

### 2. Access Control Wiring
- **`accounts/permissions.py`**
  - `can_access()` now delegates to `can_access_via_enterprise()`
  - `allowed_dashboard_url_name()` uses enterprise dashboard routing
  - `can_manage_user_approvals()` checks `approval` / `user_management` permissions
  - `can_manage_users()` checks `user_management` permission
  - Added `MODULE_GPS_TRACKING` for `/productivity/gps/` paths

### 3. Permission-Driven Navigation
- **`accounts/context_processors.py`** — builds `enterprise_nav_sections` via `build_navigation_menu()`
- **`templates/base.html`** — sidebar renders from `enterprise_nav_sections` (replaces hardcoded menu)
- Legacy `show_nav_*` flags retained for dashboard templates (derived from nav + permission helpers)

### 4. Dashboard Integration
- **`dashboard/views.py`** — director, operations, accounts, and PM dashboards use `dashboard_widget_flags()`
- Widget visibility (operations, financial, quotations, KPIs) driven by individual grants

### 5. GPS & Productivity Gates
- **`productivity/permissions.py`** — GPS dashboard gated on `gps_tracking` permission
- Management productivity gated on `reports` + role-equivalent permission combinations

### 6. Registration & Approval
- **`accounts/forms.py`** — registration uses Department, Designation, Branch, Employment Type
- Removed `role_requested`; creates pending `Employee` profile on submit
- **`templates/accounts/register.html`** — updated fields
- **`accounts/enterprise_approval.py`** — assigns default permissions from designation on approval
- **`accounts/approval_services.py`** — activates Employee + grants permissions on approve

### 7. Cache Invalidation
- **`accounts/signals.py`** — clears permission cache on grant save/delete
- **`accounts/admin.py`** — clears cache when grants edited inline
- **`accounts/apps.py`** — registers signals on startup

### 8. Migration
- **`accounts/migrations/0010_phase2_permission_menu_urls.py`** — populates `menu_url_name` / `menu_icon` on permissions

---

## How Access Works Now

```
Request → Middleware → can_access() → can_access_via_enterprise()
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    │                                                   │
            Has Employee profile?                              No profile
                    │                                                   │
         enterprise_module_grants_access()                  legacy_module_grants_access()
         (maps MODULE_* → permission codename)              (User.role + _ACCESS matrix)
```

**Priority:** Individual `EmployeePermissionGrant` records take precedence when an Employee profile exists. Legacy `User.role` is fallback only.

---

## Navigation Catalog

Menu items are defined in `NAV_MENU_CATALOG` (`enterprise_permissions.py`). Each entry requires a permission codename. Extra visibility rules apply for:
- My Attendance (`attendance_required` flag)
- Attendance Management / Team Attendance (attendance module helpers)
- Doc Numbers (superuser or `user_management`)
- Productivity, GPS, ERMS, Daily Meetings (module-specific helpers)

---

## Dashboard Routing

| Permission Pattern | Dashboard |
|-------------------|-----------|
| `user_management` or `reports` + `billing` | Director |
| `billing`/`payments`/`accounts` without `orders` | Accounts |
| `orders` + `scheduling`/`wcr` without `quotation` | Field Team |
| `orders` + `approval` + `scheduling` | Supervisor |
| `orders` (general ops) | Operations |
| `dashboard` only | Director |
| No matching permissions | Login (denied) |

---

## Registration Flow (Updated)

1. User submits registration with Department + Designation (no role dropdown)
2. System creates inactive `User` + pending `Employee` (status INACTIVE, no permissions)
3. Admin approves → Employee activated + default permissions assigned from designation
4. User can sign in; menu and dashboards reflect individual grants

---

## Files Created / Modified

| File | Action |
|------|--------|
| `accounts/enterprise_permissions.py` | **Created** — permission service (Phase 2 core) |
| `accounts/enterprise_approval.py` | **Created** — default grants on approval |
| `accounts/signals.py` | **Created** — cache invalidation |
| `accounts/enterprise_constants.py` | **Modified** — GPS mapping, designation→role map |
| `accounts/permissions.py` | **Modified** — enterprise bridge |
| `accounts/context_processors.py` | **Modified** — permission-driven nav |
| `accounts/forms.py` | **Modified** — dept/designation registration |
| `accounts/approval_services.py` | **Modified** — activate employee on approve |
| `accounts/admin.py` | **Modified** — cache invalidation on grant edit |
| `accounts/apps.py` | **Modified** — signal registration |
| `accounts/migrations/0010_phase2_permission_menu_urls.py` | **Created** |
| `templates/base.html` | **Modified** — dynamic nav |
| `templates/accounts/register.html` | **Modified** — new fields |
| `dashboard/views.py` | **Modified** — widget flags |
| `productivity/permissions.py` | **Modified** — GPS gate |

### NOT Modified (Phase 3 scope)
- Removal of `User.role` field and `_ACCESS` matrix
- Decorator/middleware refactor to codename-only checks
- Full RBAC admin UI for non-superusers

---

## Verification Commands

```bash
python manage.py migrate accounts
python manage.py check
python manage.py shell -c "
from accounts.models import User
from accounts.enterprise_permissions import get_user_permission_codenames, build_navigation_menu
u = User.objects.filter(is_superuser=False, is_active=True).first()
print('User:', u.username)
print('Permissions:', sorted(get_user_permission_codenames(u)))
print('Nav sections:', len(build_navigation_menu(u)))
"
```

---

## Review Checklist

- [ ] Sign in as different employees — verify sidebar matches their grants
- [ ] Remove a permission in Admin → Employee → Grants — menu item should disappear after refresh
- [ ] Register new user with Department/Designation — approve — verify default access
- [ ] GPS menu visible only for users with `gps_tracking` grant
- [ ] Dashboard widgets hide sections user cannot access
- [ ] Legacy users without Employee profile still work (fallback path)

---

**STOP HERE** — Phase 3 (legacy role removal) should not begin until Phase 2 is reviewed and approved.
