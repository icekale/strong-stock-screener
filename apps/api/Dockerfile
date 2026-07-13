FROM python:3.12-slim AS api-builder

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=$PIP_INDEX_URL \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10

WORKDIR /build/api

COPY pyproject.toml uv.lock ./
RUN python -m venv /opt/strong-stock-api-venv \
    && /opt/strong-stock-api-venv/bin/python -m pip install --no-cache-dir setuptools wheel pydantic-core==2.46.4 uv==0.11.6 \
    && /opt/strong-stock-api-venv/bin/uv export --locked --no-dev --no-emit-project --format requirements-txt -o requirements.txt \
    && /opt/strong-stock-api-venv/bin/python -m pip uninstall -y uv \
    && /opt/strong-stock-api-venv/bin/python -m pip install --no-cache-dir --no-build-isolation -r requirements.txt
COPY app ./app
RUN /opt/strong-stock-api-venv/bin/python -m pip install --no-cache-dir --no-deps --no-build-isolation .


FROM python:3.12-slim AS rc8-builder

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=$PIP_INDEX_URL \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10

WORKDIR /build/rc8

COPY rc8-worker/pyproject.toml rc8-worker/uv.lock ./
RUN python -m venv /opt/czsc-rc8-venv \
    && /opt/czsc-rc8-venv/bin/python -m pip install --no-cache-dir setuptools==83.0.0 wheel==0.47.0 uv==0.11.6 \
    && /opt/czsc-rc8-venv/bin/uv export --locked --no-dev --no-emit-project --format requirements-txt -o requirements.txt \
    && /opt/czsc-rc8-venv/bin/python -m pip uninstall -y uv \
    && /opt/czsc-rc8-venv/bin/python -m pip install --no-cache-dir --no-build-isolation -r requirements.txt \
    && /opt/czsc-rc8-venv/bin/python -c "import czsc; import importlib.metadata; assert importlib.metadata.version('czsc') == '1.0.0rc8'"


FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/strong-stock-api-venv/bin:$PATH

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=api-builder /opt/strong-stock-api-venv /opt/strong-stock-api-venv
COPY --from=rc8-builder /opt/czsc-rc8-venv /opt/czsc-rc8-venv
COPY app ./app
COPY artifacts ./artifacts

RUN python -c "import czsc, mootdx; print(czsc.__version__, mootdx.__version__)" \
    && python -c "import importlib.metadata; assert importlib.metadata.version('czsc') == '0.10.12'" \
    && /opt/czsc-rc8-venv/bin/python -c "import czsc; import importlib.metadata; assert importlib.metadata.version('czsc') == '1.0.0rc8'"

EXPOSE 8010

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
