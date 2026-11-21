# RosterFlow – Approach note

## Short version (for the submission email)

RosterFlow treats rostering as a constraint problem: each brand × process has its own operating calendar and
minimum staffing, and a deterministic engine places mandatory weekly offs where they hurt coverage least
(client coverage always outranks preferred days), then fills gaps with designated backups. An independent
validator re-checks every generated or manually edited roster, explains each gap or rule violation with ranked
one-click cover suggestions, and blocks publishing until errors are resolved or explicitly accepted. Changes such as
newly approved leave are analysed before they are applied, flow into a new draft revision (never the live roster),
and the rest of the month can be re-optimised while keeping past days and manual edits.

## Problem framing

* **Demand** comes from clients: brand × process, per weekday, holidays, sale-day overrides.
* **Supply** comes from people: assignments (primary / backup), weekly-off rules, leave, comp-offs.
* A roster is valid when every operating scope-day has at least its minimum staff, without breaking approved leave,
  fixed offs, weekly rest or shift limits. Preferences are soft.

## Key decisions

| Decision | Why |
|---|---|
| Keep Flask + MySQL (existing stack) | Assessment allows any stack; continuing the existing project avoided a rewrite and kept effort on the scheduling logic. |
| Deterministic greedy + repair + backup covers, not a black-box solver | Fast (< 1 s for 34 × 31), explainable to an ops manager ("the off moved to Tuesday because Sunday had no cover"), easy to unit-test. A CP-SAT model is the documented next step at larger scale. |
| Separate validator from generator | The same rules check generated rosters, manual edits, old rosters after rule changes, and what-ifs; the generator can never hide a gap. |
| One table for staffing (`Assignment` with primary/backup role) | Expresses single-resource brands, separate processes, shared processes and multi-brand people without special cases. |
| Per-weekday minimum pattern + date overrides | Covers 365-day, daily-except-holidays, Mon–Sat, "2 on weekdays / 1 at weekends" and sale days with one concept. |
| Versioned rosters (draft → published → archived, revisions) | Published rosters are never edited in place; every change is a reviewable, comparable revision with a change log. |
| Humans approve, system proposes | Leave approval, covers outside the designated backup, risk acceptance and publishing are explicit logged actions. |
| AI only explains | Claude (optional) turns a structured conflict into plain English; it never makes scheduling decisions, and a rule-based explanation is used when no key is configured. |

## Verification

* 14 unit tests on the pure scheduling core (rest, preferences vs coverage, per-day minimums, holidays, overrides,
  backups, shift compatibility, multi-brand impact, locked cells, manual-edit validation).
* 13 integration tests through HTTP: seed structure matches the brief's 80/20 pattern, every page renders, edits
  re-validate, covers resolve gaps, publishing is gated, change-after-publication creates a revision, shared brands
  absorb one absence, re-optimisation keeps manual edits, rule changes are picked up by re-validation.
* Manually exercised on MySQL/MariaDB with gunicorn and a headless browser (desktop + mobile).
