# Local / cloud-friendly single-service image for moderated pilots.
# Build: docker build -t medastrax .
# Run:   docker run --rm -p 8000:8000 -e HC_STUDY_MODE=true -e HC_ALLOW_LOGISTIC_FALLBACK=true medastrax
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

FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=backend /opt/venv /opt/venv
COPY --from=backend /app/backend /app/backend
COPY --from=frontend /frontend/dist /app/frontend/dist
COPY study ./study
COPY scripts ./scripts
ENV PATH="/opt/venv/bin:$PATH"
ENV HC_API_HOST=0.0.0.0
ENV HC_API_PORT=8000
EXPOSE 8000
CMD ["uvicorn", "hc_analytics.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
