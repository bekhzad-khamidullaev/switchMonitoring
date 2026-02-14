# Docker Compose Setup

## Services
- `web`: Django app (`runserver`), applies migrations and collects static on start.
- `db`: PostgreSQL 15.
- `redis`: broker/result backend for Celery.
- `celery_worker`: background worker.
- `celery_beat`: scheduler for discovery/polling tasks.

## Run
```bash
docker compose up --build
```

Django will be available on `http://localhost:8000`.

## Useful commands
```bash
# stop stack
docker compose down

# stop and remove data volumes
docker compose down -v

# run tests inside container
docker compose run --rm web python manage.py test
```
