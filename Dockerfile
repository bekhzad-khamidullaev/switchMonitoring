FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --uid 10001 --create-home app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . /app

RUN chmod +x /app/docker/entrypoint-web.sh /app/docker/entrypoint-prod-web.sh
RUN mkdir -p /app/static_files /app/media /app/.cache \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["/app/docker/entrypoint-web.sh"]
