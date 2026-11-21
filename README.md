# RosterFlow – Smart Roster Management System

A browser-based tool that helps an operations manager **plan, generate, validate and manage monthly rosters**
for a customer-experience team that serves many D2C brands across processes (CS, ACC, NDR, Retention, Reviews)
and operational pods.

Built for the DataStraw *Smart Roster Management System* assessment with **Python · Flask · MySQL · HTML/CSS/JS**.

| | |
|---|---|
| **Live demo** | `<add your deployed URL here>` – see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| **Demo video** | `<add your video link here>` – script in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |
| **Approach note** | [docs/APPROACH.md](docs/APPROACH.md) |
| **Tests** | `pytest` – 27 tests (scheduling core + end-to-end flows) |

> The problem is treated as a **scheduling problem, not a calendar**: brand calendars create *demand*, people create
> *supply*, a deterministic engine matches them, and an independent validator explains every gap instead of hiding it.

---

## 1. What it does (mapped to the brief)

| Brief requirement | Where / how |
|---|---|
| Central database of employees, brands, processes, pods, pod leads, allocations | *Employees*, *Brands & Processes*, *Pods & Assignments* pages. Assignments are **Primary** (count towards coverage) or **Backup** (used only to cover gaps); effective-dated. |
| Working-day rules & minimum coverage per brand **and** process | *Working Rules*: per-weekday minimum staff (0 = closed), public-holiday flag, shift hours, effective dates; presets for 365-day / daily-except-holidays / Mon–Sat / Mon–Fri. **Date-specific overrides** for sale days or closures. |
| Availability, weekly offs, planned leave, comp-offs, public holidays | *Leave & Availability* (pending → approved workflow), *Weekly Offs* (**Fixed** = hard, **Preferred** = soft), per-employee weekly-offs-per-week, *Public Holidays*. |
| Generate a monthly roster | *Rosters → Generate*: creates a versioned **DRAFT** in ~1 s for 34 people × 31 days. |
| Views: company, pod, brand, process, employee (+ day) | Roster page tabs. Company view shows a **brand-coverage heat-map** (staff ÷ required per day) and the full employee grid grouped by pod. Day view answers "who is working today and is every brand covered?". |
| Conflicts & coverage gaps before publishing | **Conflicts** tab: 10 conflict types, ERROR / WARNING / INFO, each with an explanation, a suggestion and one-click cover candidates. Publishing is **blocked** while errors are open, unless the manager explicitly accepts them. |
| Manual changes + validation of their impact | Click any grid cell → change status → the whole roster is re-validated and the flash message says how many errors were created/resolved. Add/remove covers from the day view or a conflict. Full **change log**. |
| Handle changes without rebuilding | *Change impact* page (what-if), automatic impact check when leave is approved, *Apply to roster* (published rosters get a new draft revision), *Re-validate* after rule changes, *Re-optimise from date* (keeps past days + manual edits), *Compare versions*. |
| ≥ 30 employees, realistic structure | Seeded: **34 employees, 5 pods with leads, 28 brands, 5 processes**. 23/28 brands (82 %) are single-resource; 5 brands have 2–3 people (separate processes, shared processes, and both). |
| Optional extras | Fair weekly-off distribution, preference-based scheduling, backup recommendations & auto-cover, regeneration after leave, version comparison, draft → published approval workflow with acknowledgement, change log, CSV export (opens in Excel/Sheets), AI-assisted conflict explanations (Claude API, with rule-based fallback). |

---

## 2. Architecture

```
app/
├── scheduling/            ← the core, pure Python (no Flask/DB imports in the first four)
│   ├── scenario.py        inputs for one month + lookups (demand, duties, availability, weeks)
│   ├── engine.py          roster generator (weekly-off placement, repair, backup covers)
│   ├── validator.py       independent rule checker + cover-candidate ranking
│   ├── plan.py            in-memory roster (day statuses + covers) and duty expansion
│   ├── loader.py          database → Scenario
│   ├── service.py         lifecycle: generate, edit, cover, publish, revise, re-optimise, impact
│   └── views.py           roster → data for the company/pod/brand/process/employee/day screens
├── models/                SQLAlchemy models (MySQL in production, SQLite in tests)
├── routes/                Flask blueprints (one per screen)
├── services/ai_explainer.py   optional Claude explanation of a conflict
├── templates/ static/     server-rendered HTML, one CSS file for the roster UI, ~80 lines of JS
└── seed.py                demo dataset
tests/                     unit tests for the engine + integration tests through the HTTP layer
database/schema.sql        reference MySQL DDL generated from the models
```

* **Server-rendered Flask** keeps the app small, fast and easy to deploy; JavaScript is only progressive
  enhancement (edit dialog, CSRF token, AI explanation fetch). Every action is a normal form POST.
* The scheduling core has **no database dependency**, so the rules are unit-tested directly
  (`tests/test_engine.py`) and the same validator checks generated, edited and old rosters.
* Every roster is an immutable-once-published **version**: `DRAFT → PUBLISHED → ARCHIVED`, with
  `parent_version_id` for revisions and re-optimisations.

### Data model

```
Pod 1─* Employee (pod lead = Pod.lead_employee_id)
Employee *─* Brand×Process  via Assignment(priority 1 = primary, 2 = backup, effective dates)
Brand×Process 1─* WorkingRule(daily_minimums "Mon..Sun", operates_public_holidays, shift, dates)
Brand×Process 1─* CoverageOverride(date, minimum_staff, reason)
Employee 1─* EmployeeWeeklyOff(weekday, FIXED|PREFERRED)   Employee.weekly_offs_per_week
Employee 1─* Availability(PLANNED_LEAVE|COMP_OFF|UNAVAILABLE, PENDING|APPROVED|REJECTED)
Holiday(date, name)
RosterVersion 1─* RosterDay(employee, date, status, AUTO|MANUAL, note)   ← who works / who is off
              1─* RosterEntry(employee, brand, process, date, shift, is_cover) ← what they cover
              1─* Conflict(type, severity, message, suggestion, candidates, acknowledged)
              1─* RosterChangeLog
```

The **brand's operating calendar** (WorkingRule / overrides / holidays) is deliberately separate from the
**employee's schedule** (RosterDay), exactly as the brief asks.

---

## 3. How a roster is generated

1. **Demand** – for every active brand × process and day: the weekday minimum from its rule, `0` on public
   holidays unless it operates on holidays, replaced by a date override when one exists.
2. **Hard availability** – approved leave / comp-off / unavailability, FIXED weekly offs, days on which none of an
   employee's brands operate (they become that person's natural off day), and cells locked by the manager.
3. **Mandatory weekly rest** – each employee gets `weekly_offs_per_week` rest days per Mon–Sun week (partial weeks
   pro-rated). Offs are placed greedily, **most-constrained employee first**, on the cheapest day:

   | Effect of giving the off on that day | Cost |
   |---|---|
   | leaves a brand/process below minimum and nobody can cover | 1000 |
   | leaves a gap but a colleague who knows the process is working | 300 |
   | leaves a gap but a designated backup is working | 100 |
   | not the employee's **preferred** off day | 10 |
   | fairness: spread offs across the week, rotate Sundays | < 5 |

   Because coverage costs dominate preference costs, **a required client coverage day always beats a preferred
   weekly off** – and the employee gets a `PREFERENCE_VIOLATION` warning explaining why.
4. **Repair** – for any remaining gap, try to move an auto-placed off to another day in the same week that creates
   no gap.
5. **Backup covers** – designated backups who are working, under the per-day cover limit and with a compatible
   shift are assigned automatically.
6. **Validate** – anything still unsatisfied becomes a conflict. Nothing is silently dropped.

The manager can then: use the one-click candidate on a conflict, press **Auto-assign covers** (applies the
best-ranked compatible candidate to every gap), edit cells, acknowledge risks, and publish.

### Conflict types

| Type | Severity | Meaning |
|---|---|---|
| `COVERAGE_GAP` | ERROR | Brand/process below its minimum on an operating day (message lists who is off and why). |
| `UNASSIGNED_REQUIREMENT` | ERROR | The scope operates but nobody is assigned to it. |
| `LEAVE_CONFLICT` | ERROR | Rostered to work during approved leave/comp-off. |
| `RULE_VIOLATION` | ERROR | Rostered on a FIXED (contractual) weekly off. |
| `DOUBLE_BOOKING` | ERROR / WARNING | Covering while off, or more covers than the per-day limit. |
| `INCOMPATIBLE_SHIFT` | ERROR | The employee's duties span longer than the max shift (e.g. 07:00 + 22:00 shifts). |
| `MULTI_BRAND_IMPACT` | WARNING | One person's absence leaves several brands short the same day. |
| `REST_VIOLATION` | WARNING | Fewer weekly offs than required (usually after manual edits). |
| `PREFERENCE_VIOLATION` | WARNING | Preferred off not granted because coverage took priority. |
| `COMP_OFF_ELIGIBLE` | INFO | Worked a public holiday. |

---

## 4. Assumptions (all configurable in the UI or `.env`)

* A working employee covers **all** of their primary brand/process duties that operate that day (this is how a
  dedicated brand owner actually works); shift windows come from each process's rule.
* An employee's duties on a day must fit within `MAX_SHIFT_SPAN_HOURS` (default 9 h); each person may take
  `MAX_COVERS_PER_DAY` (default 1) extra cover duty.
* Weekly rest: default 1 off per Mon–Sun week, per-employee configurable; closed days and public holidays count as
  rest, leave and comp-off do not. A week straddling two months belongs to the month containing its Sunday.
* Only **approved** leave is a hard constraint; pending requests are visible and can be analysed before approval.
* Public holidays are company-wide (the `region` column is stored for future regional calendars).
* Covers are only proposed from people already working that day – the system never cancels someone's rest.
* Validation always runs against the **current** configuration, so changing a rule and pressing *Re-validate*
  shows its impact on an existing roster.

---

## 5. Run it locally

Requirements: Python 3.11+, MySQL 8 or MariaDB 10.6+.

```bash
git clone https://github.com/ansh12639/RosterFlow.git
cd RosterFlow
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # then edit DATABASE_URL
```

Create the database and a user (once):

```sql
CREATE DATABASE rosterflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'roster_user'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL ON rosterflow.* TO 'roster_user'@'localhost';
```

Create tables and load the demo data (34 employees, rosters for this month and next):

```bash
flask seed-demo          # drops & recreates all tables, then seeds
python run.py            # http://127.0.0.1:5000
```

Other commands: `flask init-db` (create tables only), `flask generate-roster 2026 12`.
Health check: `GET /health`. Set `AUTO_SEED=1` to seed automatically on first start with an empty database.

Run the tests (they use in-memory SQLite, no MySQL needed):

```bash
pytest
```

---

## 6. Tell us how you think

**1. How did you model employees, brands, processes, pods, and their relationships?**
Pods own employees and point to one employee as lead. The pivotal entity is the **Assignment** – an
effective-dated link from an employee to a *brand × process* pair with a role: *primary* (counts towards coverage)
or *backup* (used only to fill gaps). This one table expresses every staffing pattern in the brief: a single owner
of all of a brand's processes, several people on different processes, several people sharing one process, and
people across several brands. Demand lives separately on the brand × process pair (**WorkingRule** with a
seven-value minimum-staff pattern + **CoverageOverride** for specific dates), so a brand's operating calendar never
gets confused with an employee's schedule. A generated roster stores two things: what each person is doing each day
(**RosterDay**) and which duties/covers they perform (**RosterEntry**).

**2. How does your system generate a roster and determine whether it satisfies the required constraints?**
It computes demand per scope-day, fixes hard availability, then places mandatory weekly offs with a cost function
that makes coverage outrank preferences (section 3), repairs remaining gaps by moving offs, and assigns designated
backups. A **separate validator** then re-checks the result against every rule – coverage per brand/process/day,
leave, fixed offs, shift span, double booking, weekly rest, preferences – and stores each failure as a typed
conflict. Because the validator is independent of the generator, it also checks manual edits, old versions after
rules change, and what-if scenarios.

**3. How did you handle the difference between single-resource brands and brands with multiple employees?**
Both use the same model; the engine sees the difference through coverage. For shared scopes it staggers weekly
offs so the remaining people keep the minimum (e.g. GlowVeda needs 2 on weekdays and 1 at weekends, so offs land
on weekends). For single-resource scopes, any off on an operating day necessarily opens a gap, so the engine puts it
where it is cheapest to cover – a day the brand is closed, or a day a backup or a colleague who knows the process
is working – and assigns the backup automatically. Brand pages label every brand *Single resource* or *Shared*,
and the impact screen says "Single resource" vs "Shared – remaining staff can cover".

**4. What happens when an employee manages all processes for a brand but is unavailable on a required working day?**
Every process of that brand drops to 0/1 on that day. The validator raises one `COVERAGE_GAP` per process with the
reason ("its only assignee X is unavailable – approved leave"), adds a `MULTI_BRAND_IMPACT` warning if the person
also runs another brand, and ranks cover candidates: designated backup → same pod and knows the process →
knows the process elsewhere → same pod, excluding anyone whose shift would become too long or who already has a
cover that day. The manager assigns one with a click (or *Auto-assign covers*), and the roster is re-validated.
If nobody qualifies (e.g. the evening-shift GreenLeaf brand in the demo) it stays an explicit error, with advice to
move a weekly off or add a backup.

**5. How does your system handle conflicting requirements or insufficient staffing?**
It distinguishes **mandatory** constraints (approved leave, fixed offs, weekly rest, minimum staffing, shift span)
from **preferences** (preferred off days). Rest and leave are never violated automatically; when they collide with
coverage the engine minimises the damage and *reports* the remaining gap instead of producing an invalid roster.
Preferences always yield to client coverage and are reported as warnings. A roster with open errors cannot be
published unless the manager ticks an explicit "I accept the open errors" box, which is recorded in the change log.

**6. Which parts did you automate, and which did you leave under human control? Why?**
Automated: demand calculation, weekly-off placement, fairness, designated-backup covers, validation, impact
analysis, candidate ranking, re-optimisation of the rest of the month. Human-controlled: approving leave, applying a
change to a roster, choosing non-designated covers (one click, or a bulk "Auto-assign" the manager triggers),
overriding statuses, acknowledging unresolved risks, publishing. The split follows accountability: the system does
the combinatorial work, but anything that changes a commitment to a client or asks extra work of a person stays an
explicit, logged decision. Generated drafts never change a published roster – changes go to a new revision.

**7. If the company doubled its team and brand count, what would you change?**
The engine is roughly linear in employees × days × duties and handles today's data in about a second, so 70 people
is fine. Beyond that: (a) replace the greedy placement with a CP-SAT/ILP model (OR-Tools) using the same
constraint definitions, keeping the greedy engine as a fast fallback; (b) move generation to a background job queue;
(c) add per-pod rosters and role-based access so pod leads approve their own pod's changes; (d) regional holiday
calendars and multiple shift patterns per process; (e) Alembic migrations instead of `create_all`, and indexes on
version/date already in place.

**8. If you had one additional week, what would you improve first?**
A proper optimiser for fairness across the month (equal Sunday/holiday duty, minimising consecutive working days),
pod-lead approval flow with notifications (email/Slack via webhooks) when a published roster changes, a
drag-and-drop swap between two employees, and Google Sheets export – in that order, because the first two directly
reduce manual work for the operations manager.

---

## 7. Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for step-by-step guides (PythonAnywhere with its bundled MySQL, or
Render + a hosted MySQL). In short: set `DATABASE_URL`, `SECRET_KEY`, `AUTO_SEED=1`, and start with
`gunicorn --preload run:app` (Procfile included). The first boot creates the tables and loads the demo data.

## 8. Security notes

CSRF protection on every form (Flask-WTF), secrets only via environment variables (`.env` is git-ignored),
server-side validation on every input, parameterised queries via SQLAlchemy. The public demo has no login by design
(as the brief asks for a tool reviewers can test immediately) and offers a **Reset demo data** button; set
`ALLOW_DEMO_RESET=0` in a real deployment and put it behind SSO.
