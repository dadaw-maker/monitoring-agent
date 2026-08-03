# Build context is the MonitoringAgent/ directory (see docker-compose.yml and infra/).
FROM python:3.12-slim AS base

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY services/agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/ordermgmt_common ./ordermgmt_common
COPY services/agent/app ./app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
