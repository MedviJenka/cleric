# syntax=docker/dockerfile:1

FROM python:3.13-slim AS healer

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src ./src
COPY tests ./tests
COPY settings.py main.py README.md PLAN.md ./
COPY docs ./docs

RUN mkdir -p artifacts/workflow-runs

CMD ["uv", "run", "python", "-m", "unittest", "discover", "-s", "tests"]

FROM node:20-bookworm-slim AS food_app

WORKDIR /workspace/food_app

ENV HOST=0.0.0.0 \
    PORT=3000 \
    BROWSER=none \
    CI=true \
    WDS_SOCKET_PORT=3000

COPY food_app/package.json food_app/package-lock.json ./
RUN npm ci

COPY food_app/public ./public
COPY food_app/src ./src

EXPOSE 3000

CMD ["npm", "start"]
