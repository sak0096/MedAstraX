# Local / Azure App Service single-origin image for synthetic technical testing.
# Build: docker build -t medastrax .
# This image is not participant-ready without the release-manifest assets and
# production configuration gates described in docs/AZURE_DEPLOYMENT.md.
#
# NOTE: Mount or bake processed data + model artifacts before recruitment.
# XGBoost requires libgomp in the image (installed below).

FROM python:3.12-slim AS backend
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 build-essential \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements-lock.txt backend/pyproject.toml backend/README.md ./backend/
COPY backend/src ./backend/src
RUN python -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir -r backend/requirements-lock.txt \
  && /opt/venv/bin/pip install --no-cache-dir -e "./backend"

FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN groupadd --system medastrax \
  && useradd --system --gid medastrax --home-dir /app medastrax \
  && mkdir -p /app/runtime \
  && chown medastrax:medastrax /app/runtime
COPY --from=backend /opt/venv /opt/venv
COPY --from=backend /app/backend /app/backend
COPY --from=frontend /frontend/dist /app/frontend/dist
COPY study ./study
COPY scripts ./scripts
ENV PATH="/opt/venv/bin:$PATH"
ENV HC_API_HOST=0.0.0.0
ENV HC_API_PORT=8000
ENV HC_FRONTEND_DIST=frontend/dist
ENV HC_ASSET_ROOT=study
ENV PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
USER medastrax
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"
CMD ["uvicorn", "hc_analytics.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
