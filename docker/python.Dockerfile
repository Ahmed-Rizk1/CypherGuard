# SecureNet SOC — Multi-stage Python Dockerfile
# Builds all Python services from a single Dockerfile with target stages

FROM python:3.11-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared module (used by all services)
COPY shared/ /app/shared/
COPY manage.py /app/manage.py
COPY simulator/ /app/simulator/
COPY ml_engine/ /app/ml_engine/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini

# ===================================================================
# Service-specific stages
# ===================================================================

FROM base AS sniffer
COPY sniffer/ /app/sniffer/
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "print('sniffer alive')" || exit 1
CMD ["python", "-m", "sniffer.main"]

FROM base AS extractor
COPY extractor/ /app/extractor/
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1
CMD ["python", "-m", "extractor.main"]

FROM base AS ml_engine
COPY ml_engine/ /app/ml_engine/
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1
CMD ["python", "-m", "ml_engine.main"]

FROM base AS llm_analyzer
COPY llm_analyzer/ /app/llm_analyzer/
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')" || exit 1
CMD ["python", "-m", "llm_analyzer.main"]

FROM base AS firewall
COPY firewall/ /app/firewall/
# Install iptables for optional OS-level blocking
RUN apt-get update && apt-get install -y --no-install-recommends iptables \
    && rm -rf /var/lib/apt/lists/*
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')" || exit 1
CMD ["python", "-m", "firewall.main"]

FROM base AS gateway
COPY gateway/ /app/gateway/
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS mobile_gateway
COPY mobile_gateway/ /app/mobile_gateway/
EXPOSE 8005
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')" || exit 1
CMD ["python", "-m", "mobile_gateway.main"]

FROM base AS decision_engine
COPY control_plane/ /app/control_plane/
EXPOSE 8006
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8006/health')" || exit 1
CMD ["python", "-m", "control_plane.decision_engine"]

FROM base AS decision_timeout_listener
COPY control_plane/ /app/control_plane/
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "print('timeout_listener alive')" || exit 1
CMD ["python", "-m", "control_plane.decision_timeout_listener"]

FROM base AS decision_fallback_scanner
COPY control_plane/ /app/control_plane/
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "print('fallback_scanner alive')" || exit 1
CMD ["python", "-m", "control_plane.decision_fallback_scanner"]

FROM base AS decision_log_writer
COPY control_plane/ /app/control_plane/
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "print('log_writer alive')" || exit 1
CMD ["python", "-m", "control_plane.decision_log_writer"]

FROM base AS ingest_gateway
COPY ingest_gateway/ /app/ingest_gateway/
COPY billing/ /app/billing/
EXPOSE 8007
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8007/health')" || exit 1
CMD ["uvicorn", "ingest_gateway.main:app", "--host", "0.0.0.0", "--port", "8007"]

