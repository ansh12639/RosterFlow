# Demo video script (≈ 4–5 minutes)

The brief asks the video to show: **roster generation, different brand schedules, conflict detection, and how the
application handles a change**. Record the deployed app in a 1440 px wide browser. Press *Reset demo data* on the
Overview page just before recording so the data matches this script.

| Time | Screen | What to show / say |
|---|---|---|
| 0:00 | Overview | "RosterFlow plans monthly rosters for a 34-person CX team across 28 brands and 5 pods. 82 % of brands are run by one person, the rest by 2–3 people." Point at the stats, today's coverage and pending leave. |
| 0:30 | Brands & Processes, Pods & Assignments | Staffing model column (Single resource / Shared). Assignments: **Primary** vs **Backup**; UrbanKicks has separate people for CS/ACC/NDR, FitFuel shares CS between two people. |
| 1:00 | Working Rules | **Different brand schedules**: UrbanKicks CS 365-day, GlowVeda CS needs 2 on weekdays / 1 at weekends, Mon–Sat and Mon–Fri brands, GreenLeaf evening shift 13–22. Scroll to date-specific overrides (sale days). |
| 1:30 | Rosters → Generate (next month) | Generate. "Each run creates a new draft version." Show the stats: coverage %, errors, warnings, backup covers. |
| 2:00 | Company view | Coverage heat-map: green = covered, darker green = covered by a backup, red = gap, hatched = brand closed. Employee grid grouped by pod with leads. Hover a cell for details. |
| 2:20 | Pod / Brand / Process / Employee / Day tabs | Brand-wise: GlowVeda's processes, people, gaps. Employee view: one person's working days, offs, holidays, leave. Day view: who works today and whether each brand is covered. |
| 2:50 | Conflicts tab | **Conflict detection**: a single-resource gap with the reason ("only assignee on comp-off") and ranked candidates; a preference warning ("coverage takes priority"); the GreenLeaf gap nobody can cover because of the evening shift. Click *Explain this*. Click a candidate → error count drops. Then *Auto-assign covers*: errors fall from ~33 to 4. |
| 3:30 | Leave & Availability | **Handling a change**: approve Priya Nair's pending leave → impact page shows each affected day: single-resource gap with suggested covers. Go back to the impact page and *Apply to roster*. Then, on **Change impact**, run a what-if for Lakshmi Reddy (HomeHaven CS is shared by two people) on a weekday: "Remaining staff can cover" – the one-of-several case from the brief. |
| 4:10 | Roster after change | Conflicts updated; assign the suggested cover. Click a grid cell, change a day to *Unavailable* → message "1 new error". Try *Publish* → blocked by errors; tick "I accept…" → published. *Create editable revision* → *Compare* versions. |
| 4:40 | Wrap-up | "Mandatory constraints vs preferences, explainable gaps, every change validated and versioned. Code, tests and approach note are on GitHub." |
