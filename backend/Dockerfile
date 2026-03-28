# Backend Development Dockerfile
#
# Build args for slow networks (set via docker compose / --build-arg):
#   PYTHON_IMAGE, DOCKER_CLI_IMAGE — Docker Hub mirrors, e.g. docker.m.daocloud.io/library/python:3.12-slim-bookworm
#   UV_IMAGE — ghcr.io mirror or tag for uv binary image
#   APT_MIRROR — Debian apt, e.g. mirrors.aliyun.com
#   NODESOURCE_BASE_URL — Node apt repo, e.g. https://mirrors.aliyun.com/deb.nodesource.com
#   UV_DEFAULT_INDEX — PyPI index for uv sync, e.g. https://mirrors.aliyun.com/pypi/simple/

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

# Point apt at a faster mirror (required for good speeds outside deb.debian.org edges).
# Replaces all list/sources under /etc/apt (bookworm uses debian.sources; security uses security.debian.org).
RUN if [ -n "${APT_MIRROR}" ]; then \
      find /etc/apt -type f \( -name "*.list" -o -name "*.sources" \) -exec sed -i \
        -e "s|deb.debian.org|${APT_MIRROR}|g" \
        -e "s|security.debian.org|${APT_MIRROR}|g" \
        -e "s|ftp.debian.org|${APT_MIRROR}|g" \
        {} + 2>/dev/null || true; \
    fi

# Install system dependencies + Node.js (provides npx for MCP servers)
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    gnupg \
    ca-certificates \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL "${NODESOURCE_BASE_URL}/gpgkey/nodesource-repo.gpg.key" | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] ${NODESOURCE_BASE_URL}/node_${NODE_MAJOR}.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (for DooD: allows starting sandbox containers via host Docker socket)
# Named stage required: BuildKit does not expand variables in COPY --from=
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

# Install uv (source image overridable via UV_IMAGE build arg)
COPY --from=uv-source /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy frontend source code
COPY backend ./backend

# Install dependencies with cache mount (UV_DEFAULT_INDEX → Aliyun/TUNA PyPI mirror when set)
RUN --mount=type=cache,target=/root/.cache/uv \
    sh -c "if [ -n \"${UV_DEFAULT_INDEX}\" ]; then export UV_DEFAULT_INDEX=\"${UV_DEFAULT_INDEX}\"; fi; cd backend && uv sync"

# Expose ports (gateway: 8001, langgraph: 2024)
EXPOSE 8001 2024

# Default command (can be overridden in docker-compose)
CMD ["sh", "-c", "cd backend && PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001"]
