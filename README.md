# RosterFlow — Smart Roster Management System

Flask + HTML/CSS/JavaScript + MySQL implementation of the DataStraw Smart Roster Management assessment.

## Prerequisites
- Python 3.11+
- MySQL 8+
- Git

## Local setup

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create the database and tables:

```bash
mysql -u root -p < database/schema.sql
```

Copy `.env.example` to `.env` and update `DATABASE_URL` with your MySQL username and password.

Run the app:

```bash
python run.py
```

Open http://127.0.0.1:5000. Health check: http://127.0.0.1:5000/health.

## Current implementation status
- [x] Flask application factory and configuration
- [x] MySQL schema for employees, pods, brands, processes, assignments, working rules, availability, holidays, roster versions, roster entries and conflicts
- [x] Initial dashboard shell
- [ ] SQLAlchemy models and migrations
- [ ] CRUD screens and APIs
- [ ] Sample dataset (30+ employees)
- [ ] Roster generation and validation engine
- [ ] Manual edits, publishing and reports
- [ ] Deployment and demo video

## Scheduling design
Mandatory constraints (availability, approved leave, operating days, minimum staffing, and no double-booking) must be satisfied before a roster can be published. Preferences such as preferred weekly offs are treated as soft constraints and must not override mandatory coverage.
