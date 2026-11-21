# Deploying RosterFlow

The app needs: Python 3.11+, a MySQL 8 / MariaDB database, and these environment variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `mysql+pymysql://USER:PASSWORD@HOST:3306/DBNAME?charset=utf8mb4` |
| `SECRET_KEY` | any long random string |
| `AUTO_SEED` | `1` – create tables and load demo data on first start (only if the DB is empty) |
| `ALLOW_DEMO_RESET` | `1` on the public demo (shows *Reset demo data*) |
| `MYSQL_SSL_CA` | only for hosted MySQL that requires TLS, e.g. `/etc/ssl/certs/ca-certificates.crt` |
| `ANTHROPIC_API_KEY` | optional – AI explanations of conflicts |

---

## Option A – PythonAnywhere (recommended: free, MySQL included, no cold starts)

1. Create a free account at pythonanywhere.com.
2. **Databases** tab → set a MySQL password → create a database named `rosterflow`.
   Note the host (`<username>.mysql.pythonanywhere-services.com`); the database is called `<username>$rosterflow`.
3. **Consoles** → *Bash*:
   ```bash
   git clone https://github.com/ansh12639/RosterFlow.git
   cd RosterFlow
   mkvirtualenv --python=/usr/bin/python3.11 rosterflow
   pip install -r requirements.txt
   cp .env.example .env
   nano .env   # set DATABASE_URL, SECRET_KEY, AUTO_SEED=0
   ```
   `DATABASE_URL=mysql+pymysql://<username>:<db-password>@<username>.mysql.pythonanywhere-services.com/<username>$rosterflow?charset=utf8mb4`
   (If your password contains special characters, URL-encode them.)
4. Load the data: `flask seed-demo`
5. **Web** tab → *Add a new web app* → *Manual configuration* → Python 3.11.
   * *Virtualenv*: `/home/<username>/.virtualenvs/rosterflow`
   * *Source code*: `/home/<username>/RosterFlow`
   * *Static files*: URL `/static/` → `/home/<username>/RosterFlow/app/static`
   * Edit the *WSGI configuration file* and replace its contents with:
     ```python
     import sys
     path = "/home/<username>/RosterFlow"
     if path not in sys.path:
         sys.path.insert(0, path)
     from dotenv import load_dotenv
     load_dotenv(path + "/.env")
     from run import app as application  # noqa
     ```
6. Click **Reload**. Open `https://<username>.pythonanywhere.com` and `/health`.

Updating later: `git pull` in the console, then **Reload** on the Web tab.
Note: free accounts must click "Run until 3 months from today" on the Web tab every 3 months, and
outbound internet (for the optional AI key) is limited to an allow-list.

---

## Option B – Render (web service) + hosted MySQL

1. Create a free MySQL database at **Aiven** (aiven.io → MySQL → Free plan) or **TiDB Cloud Serverless**.
   Copy host, port, user, password, database. Both require TLS.
2. On render.com → *New* → *Blueprint* → select this GitHub repo (it contains `render.yaml`).
3. Fill in `DATABASE_URL` (e.g. `mysql+pymysql://avnadmin:PASSWORD@HOST:PORT/defaultdb?charset=utf8mb4`) and
   optionally `ANTHROPIC_API_KEY`. `MYSQL_SSL_CA`, `AUTO_SEED=1` and `SECRET_KEY` are pre-set by the blueprint.
4. Deploy. The first boot creates the tables and seeds the demo data. Check `/health`.

Render's free plan sleeps after inactivity (first request can take ~50 s) – open the app once before sending
the link, or use PythonAnywhere.

---

## Any other host (Railway, a VPS, Docker…)

```bash
pip install -r requirements.txt
export DATABASE_URL=... SECRET_KEY=... AUTO_SEED=1
gunicorn --preload --workers 2 --bind 0.0.0.0:8000 run:app
```

`--preload` makes the one-time auto-seed run once before workers fork.
