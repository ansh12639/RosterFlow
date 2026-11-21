# RosterFlow – Smart Roster Management System

A web app that helps an operations manager create and manage monthly work rosters for a team that supports
many brands. It decides who works on which day, checks that every brand has enough staff, and clearly flags
any problem before the roster is published.

**Live app:** `<add your deployed URL here>`
**Demo video:** `<add your video link here>`

**Built with:** Python, Flask, MySQL, HTML, CSS, JavaScript

---

## Features

- **Team setup** – employees, pods with pod leads, brands, processes (CS, ACC, NDR, Retention, Reviews) and who works on what.
- **Brand rules** – each brand/process has its own working days, minimum staff per day, holiday rule and shift hours.
- **Availability** – weekly offs (fixed or preferred), leave, comp-offs and public holidays.
- **Roster generation** – one click creates the whole month for all employees.
- **Conflict detection** – shows every coverage gap or rule break, explains why, and suggests who can cover.
- **Views** – company, pod, brand, process, employee and single-day views.
- **Manual edits** – click any day to change it; the roster is re-checked instantly.
- **Handling changes** – see the impact of a leave before approving it, then apply it to the roster.
- **Extras** – backup suggestions, roster versions, publish approval, change log, CSV export, AI explanations of conflicts (optional).

The sample data has **34 employees, 5 pods and 28 brands**. 82% of the brands are run by one person; the rest have 2–3 people.

---

## Run it locally

You need **Python 3.11+** and **MySQL**.

```bash
git clone https://github.com/ansh12639/RosterFlow.git
cd RosterFlow
python -m venv .venv
.venv\Scripts\activate          # on Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create a MySQL database called `rosterflow`, then copy `.env.example` to `.env` and put your MySQL details in
`DATABASE_URL`.

```bash
flask seed-demo      # creates the tables and loads the sample data
python run.py        # open http://127.0.0.1:5000
```

Run the tests: `pytest`

To deploy online, use the included `Procfile` (start command: `gunicorn --preload run:app`) and set
`DATABASE_URL`, `SECRET_KEY` and `AUTO_SEED=1`.

---

## Approach note

Each brand and process has its own working days and minimum staff. When a roster is generated, the app first
blocks approved leave and fixed offs, then gives everyone their weekly off on the day that hurts coverage the
least – client coverage is always more important than an employee's preferred day off. Any remaining gaps are
filled by backup employees. A separate checker then reviews the roster, lists every problem with the reason and
suggested fixes, and stops the roster from being published until the problems are fixed or accepted by the manager.

---

## Tell us how you think

**1. How did you model employees, brands, processes, pods and their relationships?**
Employees belong to pods, and each pod has a lead. An *assignment* links an employee to a brand and a process,
as either the **main person** or a **backup**. Each brand/process has its own *working rule* (working days and
minimum staff). This handles every case: one person running a whole brand, several people on one brand, and one
person working on several brands.

**2. How does your system generate a roster and check it?**
It works out how many people each brand needs each day, marks leave and fixed offs, gives everyone their weekly
off on the safest day, then adds backups where needed. A separate checker reviews the result and lists every gap
or rule break.

**3. How did you handle single-resource brands vs brands with several employees?**
For brands with several people, weekly offs are spread out so someone is always working. For a one-person brand,
the off goes on a day the brand is closed or a backup is available, and the backup is assigned automatically.

**4. What happens when the only person on a brand is unavailable on a working day?**
The app shows a coverage gap for that brand, explains who is missing and why, and suggests the best people to
cover (backup first, then same-pod colleagues who know the process). The manager can assign one with one click.

**5. How does it handle conflicting requirements or not enough staff?**
Rules are split into **must-haves** (leave, fixed offs, weekly rest, minimum staff) and **preferences**
(preferred day off). Preferences give way to client coverage. If something still can't be satisfied, it is shown
as an error – the app never hides it, and the roster can't be published until the manager fixes or accepts it.

**6. What is automated and what is left to people?**
Automated: generating the roster, placing weekly offs, assigning backups, checking rules and suggesting fixes.
Left to the manager: approving leave, choosing covers, accepting risks and publishing – because these affect
clients and employees and should be a person's decision.

**7. What would you change if the team and brands doubled?**
Use an optimisation library (such as Google OR-Tools) for better results at scale, generate rosters in the
background, and let each pod lead manage their own pod.

**8. What would you improve first with one more week?**
Fairer distribution of Sunday and holiday work, notifications to employees when a published roster changes,
and drag-and-drop shift swaps.
