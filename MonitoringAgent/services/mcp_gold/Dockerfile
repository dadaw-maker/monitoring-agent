# Build context is the MonitoringAgent/ directory (see docker-compose.yml and infra/).
FROM python:3.12-slim AS base

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY services/mcp_gold/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/ordermgmt_common ./ordermgmt_common
COPY services/mcp_gold/app ./app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    GOLD_MODE=stub

USER app
EXPOSE 8001

CMD ["python", "-m", "app.server"]
