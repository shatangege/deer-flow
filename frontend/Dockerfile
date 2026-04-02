# Frontend Dockerfile
# Supports two targets:
#   --target dev   — install deps only, run `pnpm dev` at container start
#   --target prod  — full build baked in, run `pnpm start` at container start (default if no --target is specified)

ARG PNPM_STORE_PATH=/root/.local/share/pnpm/store
# Optional Docker Hub mirror prefix, e.g. docker.m.daocloud.io/library/node:22-alpine
ARG NODE_IMAGE=node:22-alpine
ARG COREPACK_NPM_REGISTRY=

# ── Base: shared setup ────────────────────────────────────────────────────────
FROM ${NODE_IMAGE} AS base
ARG PNPM_STORE_PATH
ARG NPM_REGISTRY
ARG COREPACK_NPM_REGISTRY
ENV PNPM_STORE_PATH=${PNPM_STORE_PATH}
ENV npm_config_registry=${NPM_REGISTRY}
ENV CI=true
# Configure corepack registry before installing pnpm so the download itself
# succeeds in restricted networks (COREPACK_NPM_REGISTRY controls where
# corepack fetches package managers from).
RUN if [ -n "${COREPACK_NPM_REGISTRY}" ]; then \
      export COREPACK_NPM_REGISTRY="${COREPACK_NPM_REGISTRY}"; \
    elif [ -n "${NPM_REGISTRY}" ]; then \
      export COREPACK_NPM_REGISTRY="${NPM_REGISTRY}"; \
    fi && \
    corepack enable && corepack install -g pnpm@10.26.2
RUN pnpm config set store-dir ${PNPM_STORE_PATH}
# Optionally override npm registry for restricted networks (e.g. NPM_REGISTRY=https://registry.npmmirror.com)
RUN if [ -n "${NPM_REGISTRY}" ]; then pnpm config set registry "${NPM_REGISTRY}"; fi
RUN if [ -n "${NPM_REGISTRY}" ]; then npm config set registry "${NPM_REGISTRY}"; fi
WORKDIR /app

# ── Deps: install dependencies once and reuse across dev/builder ─────────────
FROM base AS deps
WORKDIR /app/frontend
COPY frontend/package.json ./package.json
COPY frontend/pnpm-lock.yaml ./pnpm-lock.yaml
COPY frontend/pnpm-workspace.yaml ./pnpm-workspace.yaml
COPY frontend/.npmrc ./.npmrc
RUN --mount=type=cache,target=${PNPM_STORE_PATH},sharing=locked \
    pnpm fetch --frozen-lockfile
RUN --mount=type=cache,target=${PNPM_STORE_PATH},sharing=locked \
    pnpm install --offline --frozen-lockfile

# ── Dev: install only, CMD is overridden by docker-compose ───────────────────
FROM base AS dev
COPY frontend ./frontend
COPY --from=deps /app/frontend/node_modules /app/frontend/node_modules
COPY --from=deps /app/frontend/pnpm-lock.yaml /app/frontend/pnpm-lock.yaml
EXPOSE 3000

# ── Builder: install + compile Next.js ───────────────────────────────────────
FROM base AS builder
COPY frontend ./frontend
COPY --from=deps /app/frontend/node_modules /app/frontend/node_modules
COPY --from=deps /app/frontend/pnpm-lock.yaml /app/frontend/pnpm-lock.yaml
# Skip env validation — runtime vars are injected by nginx/container
RUN cd /app/frontend && SKIP_ENV_VALIDATION=1 pnpm build

# ── Prod: minimal runtime with pre-built output ───────────────────────────────
FROM ${NODE_IMAGE} AS prod
ARG PNPM_STORE_PATH
ARG NPM_REGISTRY
ARG COREPACK_NPM_REGISTRY
ENV PNPM_STORE_PATH=${PNPM_STORE_PATH}
ENV npm_config_registry=${NPM_REGISTRY}
RUN if [ -n "${COREPACK_NPM_REGISTRY}" ]; then \
      export COREPACK_NPM_REGISTRY="${COREPACK_NPM_REGISTRY}"; \
    elif [ -n "${NPM_REGISTRY}" ]; then \
      export COREPACK_NPM_REGISTRY="${NPM_REGISTRY}"; \
    fi && \
    corepack enable && corepack install -g pnpm@10.26.2
RUN pnpm config set store-dir ${PNPM_STORE_PATH}
RUN if [ -n "${NPM_REGISTRY}" ]; then pnpm config set registry "${NPM_REGISTRY}"; fi
RUN if [ -n "${NPM_REGISTRY}" ]; then npm config set registry "${NPM_REGISTRY}"; fi
WORKDIR /app
COPY --from=builder /app/frontend ./frontend
EXPOSE 3000
CMD ["sh", "-c", "cd /app/frontend && pnpm start"]
