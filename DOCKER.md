# Docker development

## Requirements

- Docker Desktop with Docker Compose v2

## Start Django

In PowerShell, from the repository directory:

```powershell
docker compose up --build
```

This command works with no `.env` file. To customize settings, optionally run `Copy-Item .env.example .env` first and edit `.env`. Compose defaults to SQLite, debug mode, and port 8000. The container installs `requirements.txt`, runs database migrations and collects static files on startup, then starts Django's development server. Open <http://localhost:8000/>. The project folder is mounted into the container, so code changes are picked up by Django's auto-reloader.

Create an administrator in a second terminal:

```powershell
docker compose exec web python manage.py createsuperuser
```

View logs or stop the container:

```powershell
docker compose logs -f web
docker compose down
```

SQLite uses `db.sqlite3` in the mounted project directory, so the database remains on the host when the container stops. The provided secret key and debug settings are for local development only; do not use them for a public production deployment.