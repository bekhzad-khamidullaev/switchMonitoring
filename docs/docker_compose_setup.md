# Docker Compose Setup

## Services
- `web`: Django app (`runserver`), applies migrations and collects static on start.
- `db`: PostgreSQL 15.
- `redis`: broker/result backend for Celery.
- `celery_main` / `celery_worker_ops`: ops worker for `default,discovery,maintenance` queues.
- `celery_polling` / `celery_worker_polling`: polling workers for `polling` queue.
- `celery_beat`: scheduler for poll/discovery/retention and subnet autoprovision tasks.

## Run
```bash
docker compose up --build
```

Django will be available on `http://localhost:8000`.

## Celery schedules (default)
- `poll-all-device-metrics`: periodic polling fan-out.
- `discover-all-devices`: periodic device discovery fan-out.
- `maintain-metric-samples`: retention cleanup (if enabled).
- `subnet-autoprovision`: subnet host auto-provision + optional profile auto-assign (if enabled).

## Useful commands
```bash
# stop stack
docker compose down

# stop and remove data volumes
docker compose down -v

# run tests inside container
docker compose run --rm web python manage.py test
```
