#!/usr/bin/env sh
# Verify formatter-paper container mounts and HTTP health.
# Run from this directory (docker/) with compose stack up, e.g.:
#   export HOME="${HOME:-$USERPROFILE}"  # Windows Git Bash / PowerShell users
#   export DEER_FLOW_ROOT="/absolute/path/to/deer-flow"
#   ./verify-formatter-paper-mounts.sh
#
# Optional: COMPOSE_PROJECT_NAME (default deer-flow-dev), COMPOSE_FILE (default docker-compose-dev.yaml)

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

PROJECT="${COMPOSE_PROJECT_NAME:-deer-flow-dev}"
FILE="${COMPOSE_FILE:-docker-compose-dev.yaml}"
COMPOSE="docker compose -p ${PROJECT} -f ${FILE}"

PORT="${FORMATTER_PAPER_PORT:-8765}"
FAILED=0

run() {
  printf '%s\n' "$*"
  sh -c "$*" || FAILED=1
}

echo "=== formatter-paper mount checks (${PROJECT} / ${FILE}) ==="

run "${COMPOSE} exec -T formatter-paper test -f /opt/formatter-paper/license/Aspose.Total.NET.lic"
if [ "${FAILED}" -eq 0 ]; then
  echo "OK: Aspose license file present"
else
  echo "FAIL: Aspose license missing at /opt/formatter-paper/license/Aspose.Total.NET.lic"
fi

SKIA_FAIL=0
${COMPOSE} exec -T formatter-paper test -f /opt/formatter-paper/native/libSkiaSharp.so || SKIA_FAIL=1
if [ "${SKIA_FAIL}" -eq 0 ]; then
  echo "OK: libSkiaSharp.so present (Linux native)"
else
  echo "WARN: libSkiaSharp.so missing — Linux pipeline needs it; bind-mount may only expose Windows DLLs"
fi

LDD_FAIL=0
${COMPOSE} exec -T formatter-paper sh -c "ldd /opt/formatter-paper/native/libSkiaSharp.so | grep -q 'not found'" && LDD_FAIL=1 || true
if [ "${LDD_FAIL}" -eq 0 ]; then
  echo "OK: ldd reports no missing libSkiaSharp.so dependencies"
else
  echo "FAIL: ldd reports missing dependencies for /opt/formatter-paper/native/libSkiaSharp.so"
  FAILED=1
fi

DF_FAIL=0
${COMPOSE} exec -T formatter-paper test -d /app/backend/.deer-flow || DF_FAIL=1
if [ "${DF_FAIL}" -eq 0 ]; then
  echo "OK: /app/backend/.deer-flow mounted"
else
  echo "FAIL: /app/backend/.deer-flow not available (create host backend/.deer-flow and recreate formatter-paper)"
  FAILED=1
fi

SK_DIRS_FAIL=0
${COMPOSE} exec -T formatter-paper test -d /app/skills || SK_DIRS_FAIL=1
${COMPOSE} exec -T formatter-paper test -d /mnt/skills || SK_DIRS_FAIL=1
if [ "${SK_DIRS_FAIL}" -eq 0 ]; then
  echo "OK: /app/skills and /mnt/skills mounted (same host tree as gateway / sandbox)"
else
  echo "FAIL: skills mounts missing under /app/skills or /mnt/skills"
  FAILED=1
fi

THR_FAIL=0
${COMPOSE} exec -T formatter-paper test -d /mnt/threads || THR_FAIL=1
if [ "${THR_FAIL}" -eq 0 ]; then
  echo "OK: THREADS_ROOT=/mnt/threads mounted"
else
  echo "FAIL: /mnt/threads missing (compose should bind backend/.deer-flow/threads)"
  FAILED=1
fi

if command -v curl >/dev/null 2>&1; then
  if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null; then
    echo "OK: HTTP GET http://127.0.0.1:${PORT}/health"
  else
    echo "FAIL: health check on port ${PORT}"
    FAILED=1
  fi
else
  echo "SKIP: curl not installed; run from host: curl -sf http://127.0.0.1:${PORT}/health"
fi

if [ "${FAILED}" -ne 0 ]; then
  echo "=== verification finished with FAILURES ==="
  exit 1
fi
echo "=== verification finished OK ==="
exit 0
