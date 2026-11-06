FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# collectstatic must not need real secrets or a database
RUN DJANGO_SETTINGS_MODULE=config.settings.dev DATABASE_URL=postgresql://build@localhost/build \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "-c", "gunicorn.conf.py"]
