# Build context is the MonitoringAgent/ directory (see docker-compose.yml and infra/).
FROM python:3.12-slim AS base

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY services/mcp_relex_generix/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/ordermgmt_common ./ordermgmt_common
COPY services/mcp_relex_generix/app ./app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    RELEX_MODE=stub \
    GENERIX_MODE=stub

USER app
EXPOSE 8002

CMD ["python", "-m", "app.server"]
