FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/checks.db

WORKDIR /app

ARG OFFLINE_INSTALL=0

# Copy dependencies first so application edits can reuse this build layer.
COPY requirements*.txt ./
COPY wheelhouse/ /tmp/wheelhouse/
RUN if [ "$OFFLINE_INSTALL" = "1" ]; then \
        pip install --no-cache-dir --no-index --find-links=/tmp/wheelhouse -r requirements-container.txt; \
    else pip install --no-cache-dir -r requirements-container.txt; fi \
    && rm -rf /tmp/wheelhouse \
    && groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --create-home appuser \
    && mkdir -p /app/data \
    && chown appuser:appuser /app/data

COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser templates/ templates/
COPY --chown=appuser:appuser static/ static/
COPY --chown=appuser:appuser tests/ tests/

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)" || exit 1

# Listen on all container interfaces; Compose publishes only to the host loopback.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "app:create_app()"]
