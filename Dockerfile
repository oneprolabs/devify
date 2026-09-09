# syntax=docker/dockerfile:1.6

# -----------------------------------------------------------------------------
# Backend builder image
# -----------------------------------------------------------------------------

FROM python:3.12-slim-bookworm AS backend-builder

SHELL ["/bin/bash", "-c"]

ARG APT_MIRROR_URL=https://deb.debian.org/debian
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Build tools and development headers stay in this disposable stage.
RUN set -eux; \
    sed -i \
        -e "s|http://deb.debian.org/debian|${APT_MIRROR_URL}|g" \
        -e "s|https://deb.debian.org/debian|${APT_MIRROR_URL}|g" \
        /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        libjpeg-dev \
        libmagic-dev \
        libpng-dev \
        libxml2-dev \
        libxslt1-dev \
        pkg-config \
        zlib1g-dev; \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

RUN pip install \
        --index-url "$PIP_INDEX_URL" \
        --trusted-host "$PIP_TRUSTED_HOST" \
        --timeout 120 \
        --retries 5 \
        uv \
    && python -m venv --without-pip /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv

WORKDIR /opt/devify

COPY devify /opt/devify
COPY pyproject.toml LICENSE README.md /opt/devify/

ARG DEV_MODE=0
RUN set -eux; \
    compile_options=(); \
    if [ "$DEV_MODE" = "1" ]; then \
        compile_options+=(--extra dev); \
    fi; \
    uv pip compile \
        pyproject.toml \
        -o requirements.txt \
        --index-url "$PIP_INDEX_URL" \
        --trusted-host "$PIP_TRUSTED_HOST" \
        "${compile_options[@]}"; \
    uv pip install \
        --python /opt/venv/bin/python \
        -r requirements.txt \
        --index-url "$PIP_INDEX_URL" \
        --trusted-host "$PIP_TRUSTED_HOST"

RUN rm -rf /root/.cache /tmp/* \
    && find /opt/venv -type d -name __pycache__ -prune \
        -exec rm -rf {} + \
    && find /opt/devify -type d -name __pycache__ -prune \
        -exec rm -rf {} +

# -----------------------------------------------------------------------------
# Backend runtime image
# -----------------------------------------------------------------------------

FROM python:3.12-slim-bookworm AS backend

SHELL ["/bin/bash", "-c"]

ARG APT_MIRROR_URL=https://deb.debian.org/debian
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_NO_CACHE_DIR=1 \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv

# Keep only tools and shared libraries used by the entrypoint and application.
RUN set -eux; \
    sed -i \
        -e "s|http://deb.debian.org/debian|${APT_MIRROR_URL}|g" \
        -e "s|https://deb.debian.org/debian|${APT_MIRROR_URL}|g" \
        /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        libmagic1 \
        libmariadb3 \
        mariadb-client \
        openssl; \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# Dependency installation is a build concern; omit pip and uv from runtime.
RUN rm -rf \
        /usr/local/lib/python3.12/site-packages/pip \
        /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
        /usr/local/bin/pip \
        /usr/local/bin/pip3 \
        /usr/local/bin/pip3.12

WORKDIR /opt/devify

COPY --from=backend-builder /opt/venv /opt/venv
COPY --from=backend-builder /opt/devify /opt/devify

RUN set -eux; \
    if command -v pip >/dev/null 2>&1; then \
        echo "ERROR: pip is present in the runtime image" >&2; exit 1; \
    fi; \
    if python -m pip --version >/dev/null 2>&1; then \
        echo "ERROR: python -m pip works in the runtime image" >&2; exit 1; \
    fi

RUN mkdir -p \
        /var/cache/devify \
        /var/log/celery \
        /var/log/gunicorn

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
