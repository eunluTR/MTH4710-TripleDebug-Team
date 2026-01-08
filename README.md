# Uni Clubs Management

Flask app for students, club managers, and SKS admins with RBAC, approvals, and event workflows.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

Create a `.env` file in the project root:

```
SECRET_KEY=change-me
APP_ENV=development
DATABASE_URL=sqlite:///instance/app.db
```

## Migrations

```bash
flask --app app:create_app db init
flask --app app:create_app db migrate -m "initial"
flask --app app:create_app db upgrade
```

If you have an older `instance/app.db`, rename or delete it before running the initial migration.

## Seed Admin + Demo Data

```bash
python scripts/seed.py
```

By default this creates an admin plus demo data (students, clubs, events, etc). If demo
data already exists, set `SEED_RESET=1` to recreate everything.

Set custom credentials and counts via env vars:

```
ADMIN_EMAIL=admin@university.edu
ADMIN_PASSWORD=AdminPass123
ADMIN_NAME=SKS
ADMIN_SURNAME=Admin
STUDENT_PASSWORD=StudentPass123
MANAGER_PASSWORD=ManagerPass123
SEED_STUDENTS=60
SEED_CLUBS=8
SEED_PENDING_CLUB_APPS=2
SEED_REJECTED_CLUB_APPS=2
SEED_RESET=1
```

## Run

```bash
python run.py
```

Or:

```bash
flask --app app:create_app run
```

## Tests

```bash
pytest
```

## Notes

- Club manager credentials are generated during admin approval and sent in a notification to the applicant student.
- Students and admins log in via `/auth/login`; managers use `/manager/login`.
