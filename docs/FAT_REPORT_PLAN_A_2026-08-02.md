# IOMS Functional Acceptance Test Report — Plan A (Corrected Workflow)

| Field | Value |
|-------|--------|
| **Product** | Infomates Operations Management System (IOMS) |
| **Version** | 1.4.x (local `db.sqlite3`) |
| **Test date** | 2026-08-02 |
| **Plan** | A — Real IOMS workflow (not ChatGPT Quotation-after-BOQ order) |
| **Environment** | Local Django 6 / SQLite / `127.0.0.1:8000` |
| **Method** | Automated FAT script (`scripts/fat_corrected_plan_a.py`) + code review + HTTP probes |
| **Raw results** | `docs/FAT_PLAN_A_RESULTS.json` |

---

## Executive verdict

**CONDITIONAL PASS — Ops lifecycle is integrated and stable for commit/deploy with known gaps documented.**

| Metric | Count |
|--------|------:|
| PASS | **85** |
| FAIL | **0** |
| WARNING | **6** |
| NOT_IN_SCOPE (by design / future) | **8** |
| BLOCKED | **0** |

**Ops path certified:**  
`Client → Order → Schedule → WCR → BOQ → Invoice → Payment → Dashboard`

**Sample FAT chain created/reused (not deleted):**
- Client: `FAT ABC Technologies Pvt Ltd`
- Order: `ITSPLORD26270017` → **CLOSED**
- Schedule: `ITSPLSCH26270022` (Tech1 assigned, vehicle `FAT-KL-01`)
- WCR: `ITSPLWCR26270014` (approved)
- BOQ: `ITSPLBOQ26270010` (verified)
- Invoice: `FAT-INV-26270017` — amount ₹10,500 + GST ₹1,890 = **₹12,390** — **RECEIVED**

---

## Workflow under test (corrected)

```text
Ops (primary):
  Client → Order → Schedule → field complete → WCR → approve
  → Execution BOQ → verify → Invoice → approve → Mark paid → Dashboard

Pre-sales (secondary / smoke):
  Quotations + Estimate BOQ pages load
  Enquiries UI is RETIRED (redirects to Orders) — documented WARNING
```

---

## Defect found and fixed during FAT

### DEF-001 — WCR re-save regresses billed/closed orders

| Item | Detail |
|------|--------|
| **Severity** | High (data integrity) |
| **Root cause** | `WorkCompletionReport.save()` always forced order status to `APPROVED` / `WCR_SUBMITTED`, even when order was already `BILLED` / `PAYMENT_PENDING` / `CLOSED` |
| **Evidence** | Re-saving approved WCR on paid order changed `CLOSED` → `APPROVED` |
| **Affected file** | [`wcr/models.py`](../wcr/models.py) |
| **Fix applied** | Skip order status sync when order is already in `BILLED`, `PAYMENT_PENDING`, or `CLOSED` |
| **Regression check** | After fix, `wcr.save()` leaves `CLOSED` unchanged |
| **Business logic impact** | Safe — preserves billing lifecycle; still advances `COMPLETED` → `WCR_SUBMITTED` / `APPROVED` as before |

No other business-logic changes were made. Invoice numbering logic was not modified.

---

## Step results

### STEP 1 — Login / Dashboard / Sidebar

| Role (mapped) | User | Dashboard | Sidebar | Home from Schedules | Result |
|---------------|------|-----------|---------|---------------------|--------|
| Super Admin | `surex` | `director_dashboard` | 19 items | Yes | **PASS** |
| Director | `Manoj` | `director_dashboard` | 15 items | Yes | **PASS** |
| Manager (PM) | `Jayan` | field/ops routing OK | Non-empty | Yes | **PASS** |
| Manager (Ops) | `Prathibha` | OK | Non-empty | Yes | **PASS** |
| Technician | `Tech1` | `field_team_dashboard` | Field modules only | Yes (Dashboard link present) | **PASS** |
| Accounts | `Maya` | OK | Includes finance where granted | Yes | **PASS** |

Notes:
- No bare role named “Manager” — mapped to `PROJECT_MANAGER` / `OPERATIONS`.
- Interactive password login not automated (credentials not exercised in browser); HTTP `force_login` used for page status checks.
- Technician **cannot** open Billing / Company Settings / User Approvals → redirects to `/access-denied/` (**PASS**).

### STEP 2 — Customer

| Check | Result |
|-------|--------|
| Create/reuse `FAT ABC Technologies Pvt Ltd` | **PASS** |
| Appears in client ORM / usable on orders | **PASS** |
| Dedicated client list search UI | **NOT_IN_SCOPE** (use Case Intelligence search) |

### STEP 3 — Order

| Check | Result |
|-------|--------|
| Order number auto-generation | **PASS** (`ITSPLORD26270017`) |
| Client selection | **PASS** |
| Work type (`INSTALLATION`) | **PASS** |
| Priority (free-text `High`) | **PASS** |
| Activity selection / Smart Manpower | **NOT_IN_SCOPE** (OPMS future) |
| Visible in order list HTTP 200 | **PASS** |
| Appears in scheduling after schedule create | **PASS** |

### STEP 4 — Scheduling

| Check | Result |
|-------|--------|
| Schedule number | **PASS** |
| PM / Engineer / Technician assignment | **PASS** (Tech1) |
| Vehicle | **PASS** |
| Calendar view `/scheduling/calendar/` | **PASS** (200) |
| Mentor field | **NOT_IN_SCOPE** |
| Technician schedule list | **PASS** (200) — “My Schedule” ≈ filtered Field Schedules + Field Team Dashboard |

### STEP 5 — WCR

| Check | Result |
|-------|--------|
| Create WCR + number | **PASS** |
| Materials / remarks | **PASS** |
| Approval → order progresses | **PASS** |
| Photo binary upload UI | **WARNING** (field exists; not file-uploaded in this FAT) |
| GPS on WCR form | **WARNING** (optional via productivity events) |
| Live customer signature | **NOT_IN_SCOPE** |

### STEP 6 — BOQ (execution)

| Check | Result |
|-------|--------|
| Create + line items (materials/services, qty, HSN) | **PASS** |
| Verify | **PASS** |
| Price / tax / total on BOQ | **NOT_IN_SCOPE** (rates live on Invoice) |

### STEP 7 — Quotation (pre-sales position)

| Check | Result |
|-------|--------|
| Correct pipeline position (before Order) | **PASS** (documented) |
| Quotations list page | **PASS** (200) |
| Estimate BOQ page | **PASS** (200) |
| PDF module importable | **PASS** |
| Enquiries UI | **WARNING** — **retired**; redirects to Orders |
| Full new enquiry→quote commercial create | **WARNING** — skipped to avoid duplicate commercial docs |

### STEP 8 — Invoice

| Check | Result |
|-------|--------|
| Manual FAT invoice number (unique) | **PASS** |
| GST breakdown + total | **PASS** (₹12,390) |
| Numbering conflict with FY series | **PASS** (unique constraint; FAT used distinct `FAT-INV-*` prefix; auto series untouched) |
| PDF module present | **PASS** (code) |

### STEP 9 — Payment

| Check | Result |
|-------|--------|
| Full payment → order **CLOSED** | **PASS** |
| Partial payment / outstanding amount field | **NOT_IN_SCOPE** (`PENDING` \| `RECEIVED` only) |

### STEP 10 — Dashboard

| Check | Result |
|-------|--------|
| KPI data available (orders, pending invoices) | **PASS** |
| Role dashboards HTTP 200 | **PASS** |

### STEP 11 — Navigation

| Check | Result |
|-------|--------|
| Director key pages (no 404/500) | **PASS** |
| Technician Home/Dashboard from Schedules | **PASS** |
| Never stuck without Home | **PASS** (sidebar Dashboard safety net) |

### STEP 12 — User management

| Check | Result |
|-------|--------|
| Registration page | **PASS** |
| Department / Designation / Employee masters | **PASS** (8 / 13 / 10) |
| Additional Responsibilities | **NOT_IN_SCOPE** (OPMS not built) |
| Self-service password reset | **WARNING/gap** — not a dedicated confirmed UX (admin set-password) |

### STEP 13 — Security

| Check | Result |
|-------|--------|
| Tech denied Billing | **PASS** → `/access-denied/` |
| Tech denied Company Settings | **PASS** |
| Tech denied User Approvals | **PASS** |
| Directors broader nav | **PASS** |
| Superuser full access | **PASS** |

### STEP 14 — Reports / Export

| Check | Result |
|-------|--------|
| CSV / PDF export capability (code) | **PASS** |
| Excel (.xlsx) export | **NOT_IN_SCOPE** / not implemented in app |

### STEP 15 — Performance / DB / UI / Errors

| Check | Result |
|-------|--------|
| Migrations applied | **PASS** |
| Unique keys (order_no, invoice_number, etc.) | **PASS** |
| Order→Client FK orphans | **PASS** (0) |
| N+1 deep profiling | **WARNING** (recommend debug toolbar on staging) |
| Mobile visual QA | **WARNING** (manual recommended) |
| Access denied handling | **PASS** |

---

## Issues summary

### FAIL
*None remaining after DEF-001 fix.*

### WARNING
1. WCR photo upload not file-exercised in this run  
2. GPS not mandatory on WCR form  
3. Enquiries module retired (redirect to Orders)  
4. Pre-sales commercial document create skipped (anti-duplication)  
5. N+1 not profiled  
6. Mobile responsiveness needs manual visual check  

### NOT_IN_SCOPE (product design / future)
1. Client list search box  
2. Order Activity master / Smart Manpower (OPMS)  
3. Schedule Mentor  
4. Live customer signature on WCR  
5. Price/tax on execution BOQ  
6. Partial payments  
7. Additional Responsibilities (OPMS)  
8. Excel export  

---

## Recommendations

1. **Commit DEF-001** (`wcr/models.py` status protection) before production deploy.  
2. Treat **Enquiries as retired** in user training; use **Orders + Quotations + Estimate BOQ**.  
3. Before go-live, manually verify: WCR photo upload, Invoice PDF print, Quotation PDF, mobile sidebar.  
4. Create Employee profiles for field users (Tech1 currently has **no** profile — nav works via legacy fallback).  
5. Do **not** enable partial payments / Excel / OPMS until those modules are built.  
6. Run `scripts/fat_corrected_plan_a.py` after each release as a smoke gate.  

---

## Suggested improvements (non-blocking)

| Area | Suggestion |
|------|------------|
| Clients | Add name/GST search on client list |
| Payments | Payment history table + partial amounts if finance requires |
| Scheduling | Rename UI to clarify “My Schedules” for technicians |
| Pre-sales | Remove or hide retired Enquiries menu entries if any remain |
| QA | Add Django TestCase wrapping the FAT script |
| Observability | django-debug-toolbar / query logging on staging |

---

## Code quality observations

- Dual RBAC (legacy role + enterprise grants) is transitional; Tech1 proves legacy fallback is still required.  
- Execution BOQ vs Invoice pricing split is intentional and consistent.  
- Document number generation via `document_generator` is solid; FAT used a separate `FAT-INV-*` prefix to avoid FY series collision.  
- WCR→Order status sync was the main integrity risk found; now guarded.  

---

## Deployment readiness

| Question | Answer |
|----------|--------|
| Ops workflow Client→…→Payment integrated? | **Yes** |
| Stable for Git commit? | **Yes** (include DEF-001) |
| Ready for production deploy? | **Yes, with WARNINGs accepted** — complete manual PDF/photo/mobile checklist on staging first |
| Blockers? | **None** for ops path |

---

## Sign-off checklist

- [x] Corrected workflow used (not Quotation-after-BOQ)  
- [x] One FAT sample chain only (no mass duplicate data)  
- [x] Existing records not deleted  
- [x] Invoice auto-numbering logic unchanged  
- [x] Permissions unchanged except access verified  
- [x] Defect fixed only where proven (`wcr/models.py`)  
- [x] Full report + JSON results produced  

**QA / BA / Dev conclusion:** IOMS Plan A ops lifecycle is **functionally accepted** with documented gaps. Proceed to commit DEF-001 + current sidebar nav fix; complete staging visual/PDF checklist before live cutover.
