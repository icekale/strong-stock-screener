# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS api-builder

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=$PIP_INDEX_URL \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10

WORKDIR /build/api

COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/strong-stock-api-venv \
    && /opt/strong-stock-api-venv/bin/python -m pip install setuptools wheel pydantic-core==2.46.4 uv==0.11.6 \
    && /opt/strong-stock-api-venv/bin/uv export --locked --no-dev --no-emit-project --format requirements-txt -o requirements.txt \
    && /opt/strong-stock-api-venv/bin/python -m pip uninstall -y uv \
    && /opt/strong-stock-api-venv/bin/python -m pip install --no-build-isolation -r requirements.txt
COPY apps/api/app ./app
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/strong-stock-api-venv/bin/python -m pip install --no-deps --no-build-isolation . \
    && /opt/strong-stock-api-venv/bin/python -c "import czsc, mootdx; print(czsc.__version__, mootdx.__version__)" \
    && find /opt/strong-stock-api-venv -type d -name __pycache__ -prune -exec rm -rf {} + \
    && find /opt/strong-stock-api-venv -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete


FROM python:3.12-slim AS rc8-builder

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=$PIP_INDEX_URL \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10

WORKDIR /build/rc8

COPY apps/api/rc8-worker/pyproject.toml apps/api/rc8-worker/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/czsc-rc8-venv \
    && /opt/czsc-rc8-venv/bin/python -m pip install setuptools==83.0.0 wheel==0.47.0 uv==0.11.6 \
    && /opt/czsc-rc8-venv/bin/uv export --locked --no-dev --no-emit-project --format requirements-txt -o requirements.txt \
    && /opt/czsc-rc8-venv/bin/python -m pip uninstall -y uv \
    && /opt/czsc-rc8-venv/bin/python -m pip install --no-build-isolation -r requirements.txt \
    && /opt/czsc-rc8-venv/bin/python -c "import czsc; import importlib.metadata; assert importlib.metadata.version('czsc') == '1.0.0rc8'"


FROM node:22-slim AS web-deps

WORKDIR /build/web

RUN corepack enable \
    && corepack prepare pnpm@9.15.0 --activate

COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile


FROM node:22-slim AS web-builder

WORKDIR /build/web

RUN corepack enable \
    && corepack prepare pnpm@9.15.0 --activate

COPY --from=web-deps /build/web/node_modules ./node_modules
COPY apps/web ./
ARG NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL=
ENV NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL=$NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL
RUN pnpm build \
    && test -f .next/standalone/server.js


FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    PORT=3110 \
    HOSTNAME=0.0.0.0 \
    STRONG_STOCK_DATA_DIR=/app/data \
    TZ=Asia/Shanghai

WORKDIR /app

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates libgomp1 libstdc++6 tini tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo "$TZ" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=api-builder /opt/strong-stock-api-venv /opt/strong-stock-api-venv
COPY --from=rc8-builder /opt/czsc-rc8-venv /opt/czsc-rc8-venv
COPY apps/api/app ./api/app
COPY apps/api/artifacts ./api/artifacts
COPY --from=web-builder /build/web/.next/standalone ./web
COPY --from=web-builder /build/web/.next/static ./web/.next/static
COPY scripts/start-single-container.sh ./start-single-container.sh

RUN /opt/strong-stock-api-venv/bin/python -c "import czsc, mootdx; print(czsc.__version__, mootdx.__version__)" \
    && /opt/strong-stock-api-venv/bin/python -c "import importlib.metadata; assert importlib.metadata.version('czsc') == '0.10.12'" \
    && /opt/czsc-rc8-venv/bin/python -c "import czsc; import importlib.metadata; assert importlib.metadata.version('czsc') == '1.0.0rc8'" \
    && chmod +x ./start-single-container.sh \
    && mkdir -p /app/data

EXPOSE 3110

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD /opt/strong-stock-api-venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=3).read()"

ENTRYPOINT ["tini", "--"]
CMD ["/app/start-single-container.sh"]
