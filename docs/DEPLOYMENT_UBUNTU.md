# IOMS — Ubuntu production settings (multi-environment)

This project uses:

- `config.settings.development` — local SQLite (default)
- `config.settings.production` — PostgreSQL + hardened security

Application code is unchanged; only Django settings were split.

## What to configure on Ubuntu

### 1. Code & virtualenv

```bash
cd /path/to/infomates_oms
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# PostgreSQL driver (if not already listed):
pip install psycopg[binary]
```

### 2. Environment file

```bash
cp .env.example /etc/ioms.env   # or project .env
nano /etc/ioms.env
```

Set at minimum:

| Variable | Purpose |
|----------|---------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `SECRET_KEY` | Long random secret (never reuse the insecure local key) |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | `https://your.domain.com` (comma-separated) |
| `DATABASE_NAME` | Postgres DB name |
| `DATABASE_USER` | Postgres user |
| `DATABASE_PASSWORD` | Postgres password |
| `DATABASE_HOST` | Usually `127.0.0.1` |
| `DATABASE_PORT` | Usually `5432` |

Do **not** commit `/etc/ioms.env` or `.env`.

### 3. PostgreSQL

```bash
sudo -u postgres createuser ioms_user -P
sudo -u postgres createdb -O ioms_user iomsdb
```

Backup before migrate:

```bash
sudo -u postgres pg_dump iomsdb > /root/pre_update_$(date +%Y%m%d_%H%M).sql
```

### 4. Django on the server

```bash
export $(grep -v '^#' /etc/ioms.env | xargs)
# or: set -a; source /etc/ioms.env; set +a

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_enterprise_masters
python manage.py check --deploy
```

### 5. Gunicorn / systemd example

```ini
# /etc/systemd/system/ioms.service
[Service]
WorkingDirectory=/path/to/infomates_oms
EnvironmentFile=/etc/ioms.env
ExecStart=/path/to/infomates_oms/venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 --workers 3
```

Ensure `EnvironmentFile` sets `DJANGO_SETTINGS_MODULE=config.settings.production`.

### 6. Nginx

- Proxy to Gunicorn
- Serve `/static/` from `STATIC_ROOT` (`.../staticfiles/`)
- Serve `/media/` from `MEDIA_ROOT`
- Terminate TLS; forward `X-Forwarded-Proto https`

### 7. Local development (unchanged workflow)

```bash
# default is already development
python manage.py runserver
```

Or explicitly:

```bash
set DJANGO_SETTINGS_MODULE=config.settings.development   # Windows
export DJANGO_SETTINGS_MODULE=config.settings.development  # Linux
```

## Rollback

1. Stop the app service.
2. Restore previous settings layout from git if needed:

   ```bash
   git checkout <previous-commit> -- config/settings.py config/settings/ manage.py config/wsgi.py config/asgi.py
   ```

   Or revert the whole commit.
3. Restore DB from `pg_dump` / SQLite backup taken before the update.
4. Point `DJANGO_SETTINGS_MODULE` back if you had customized it.
5. Restart the service and verify login.

## Compatibility notes

- `config.settings` still imports development settings via `config/settings/__init__.py` for older scripts.
- Prefer `config.settings.development` or `config.settings.production` explicitly.
