FROM python:3.12-slim AS api-builder

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=$PIP_INDEX_URL \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10

WORKDIR /build/api

COPY apps/api/pyproject.toml ./
COPY apps/api/app ./app
RUN python -m venv /opt/strong-stock-api-venv \
    && /opt/strong-stock-api-venv/bin/python -m pip install --no-cache-dir setuptools wheel pydantic-core==2.46.4 \
    && /opt/strong-stock-api-venv/bin/python -m pip install --no-cache-dir --no-build-isolation .


FROM node:22-slim AS web-deps

WORKDIR /build/web

RUN corepack enable \
    && corepack prepare pnpm@9.15.0 --activate

COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile


FROM node:22-slim AS web-builder

WORKDIR /build/web

RUN corepack enable \
    && corepack prepare pnpm@9.15.0 --activate

COPY --from=web-deps /build/web/node_modules ./node_modules
COPY apps/web ./
ARG NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL=
ENV NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL=$NEXT_PUBLIC_STRONG_STOCK_API_BASE_URL
RUN pnpm build


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
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates libstdc++6 tini tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo "$TZ" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=api-builder /opt/strong-stock-api-venv /opt/strong-stock-api-venv
COPY apps/api/app ./api/app
COPY --from=web-builder /build/web/package.json ./web/package.json
COPY --from=web-builder /build/web/node_modules ./web/node_modules
COPY --from=web-builder /build/web/.next ./web/.next
COPY --from=web-builder /build/web/next.config.ts ./web/next.config.ts
COPY scripts/start-single-container.sh ./start-single-container.sh

RUN chmod +x ./start-single-container.sh \
    && mkdir -p /app/data

EXPOSE 3110

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD /opt/strong-stock-api-venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=3).read()"

ENTRYPOINT ["tini", "--"]
CMD ["/app/start-single-container.sh"]
