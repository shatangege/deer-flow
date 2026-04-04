# Backend Development Dockerfile
#
# Build args for slow networks (set via docker compose / --build-arg):
#   PYTHON_IMAGE, DOCKER_CLI_IMAGE - Docker Hub mirrors, e.g. docker.m.daocloud.io/library/python:3.12-slim-bookworm
#   UV_IMAGE - ghcr.io mirror or tag for uv binary image
#   APT_MIRROR - Debian apt, e.g. mirrors.aliyun.com
#   NODESOURCE_BASE_URL - Node apt repo, e.g. https://mirrors.aliyun.com/deb.nodesource.com
#   UV_DEFAULT_INDEX - PyPI index for uv sync, e.g. https://mirrors.aliyun.com/pypi/simple/

ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.7.20
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG DOCKER_CLI_IMAGE=docker:cli
FROM ${UV_IMAGE} AS uv-source
FROM ${DOCKER_CLI_IMAGE} AS docker-cli
FROM ${PYTHON_IMAGE}

ARG NODE_MAJOR=22
ARG APT_MIRROR
ARG NODESOURCE_BASE_URL=https://deb.nodesource.com
ARG UV_DEFAULT_INDEX

ENV UV_LINK_MODE=copy

# Point apt at a faster mirror when configured.
RUN if [ -n "${APT_MIRROR}" ]; then \
      find /etc/apt -type f \( -name "*.list" -o -name "*.sources" \) -exec sed -i \
        -e "s|deb.debian.org|${APT_MIRROR}|g" \
        -e "s|security.debian.org|${APT_MIRROR}|g" \
        -e "s|ftp.debian.org|${APT_MIRROR}|g" \
        {} + 2>/dev/null || true; \
    fi

# Install system dependencies + Node.js (provides npx for MCP servers).
RUN sh -ec '\
      apt_update() { \
        attempt=1; \
        while [ "$attempt" -le 5 ]; do \
          apt-get update -o Acquire::Retries=5 && return 0; \
          sleep $((attempt * 2)); \
          attempt=$((attempt + 1)); \
        done; \
        return 1; \
      }; \
      apt_update && apt-get install -y \
        curl \
        build-essential \
        gnupg \
        ca-certificates \
        libexpat1 \
        libicu72 \
        libfontconfig1 \
        libfreetype6 \
        libpng16-16 \
        libjpeg62-turbo \
        libharfbuzz0b \
        libglib2.0-0 \
        libstdc++6 \
        libuuid1 \
        libx11-6 \
        libxau6 \
        libxcb1 \
        libxext6 \
        libxrender1 \
        zlib1g \
      && mkdir -p /etc/apt/keyrings \
      && curl -fsSL "${NODESOURCE_BASE_URL}/gpgkey/nodesource-repo.gpg.key" | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
      && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] ${NODESOURCE_BASE_URL}/node_${NODE_MAJOR}.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
      && apt_update \
      && apt-get install -y nodejs \
      && rm -rf /var/lib/apt/lists/*'

# Install Docker CLI (for DooD: allows starting sandbox containers via host Docker socket).
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

# Install uv (source image overridable via UV_IMAGE build arg).
COPY --from=uv-source /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy only dependency manifests first so uv sync stays cached across source edits.
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/uv.lock /app/backend/uv.lock
COPY backend/packages/harness/pyproject.toml /app/backend/packages/harness/pyproject.toml

# Install dependencies with cache mount.
RUN --mount=type=cache,target=/root/.cache/uv \
    sh -c "if [ -n \"${UV_DEFAULT_INDEX}\" ]; then export UV_DEFAULT_INDEX=\"${UV_DEFAULT_INDEX}\"; fi; cd backend && uv sync"

# Copy backend and custom agent source code after dependency install.
COPY backend ./backend
COPY custom_agents ./custom_agents

EXPOSE 8001 2024

CMD ["sh", "-c", "cd backend && PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001"]
