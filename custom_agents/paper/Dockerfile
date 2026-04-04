# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG DOTNET_IMAGE=mcr.microsoft.com/dotnet/runtime:8.0-bookworm-slim
ARG SKIASHARP_NATIVE_PACKAGE=SkiaSharp.NativeAssets.Linux
ARG SKIASHARP_NATIVE_VERSION=2.88.9
ARG NUGET_FLAT_CONTAINER_BASE=https://api.nuget.org/v3-flatcontainer

FROM ${PYTHON_IMAGE} AS python-runtime

FROM ${DOTNET_IMAGE}

ARG APT_MIRROR
ARG SKIASHARP_NATIVE_PACKAGE
ARG SKIASHARP_NATIVE_VERSION
ARG NUGET_FLAT_CONTAINER_BASE

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PAPER_HTTP_HOST=0.0.0.0
ENV PAPER_HTTP_PORT=8766
ENV PAPER_HTTP_PATH=/mcp
ENV PAPER_PUBLIC_BASE_URL=http://paper:8766
ENV PAPER_SERVICE_DATA_DIR=/app/custom_agents/paper/.service-data
ENV ASPOSE_MANAGED_DIR=/opt/paper-agent/managed
ENV ASPOSE_NATIVE_DIR=/opt/paper-agent/native
ENV ASPOSE_LICENSE_PATH=/opt/paper-agent/license/Aspose.Total.NET.lic
ENV ASPOSE_LIBS=/opt/paper-agent/managed
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PATH="/usr/local/bin:/usr/local/sbin:${PATH}"

COPY --from=python-runtime /usr/local /usr/local

RUN if [ -n "${APT_MIRROR}" ]; then \
      find /etc/apt -type f \( -name "*.list" -o -name "*.sources" \) -exec sed -i \
        -e "s|deb.debian.org|${APT_MIRROR}|g" \
        -e "s|security.debian.org|${APT_MIRROR}|g" \
        -e "s|ftp.debian.org|${APT_MIRROR}|g" \
        {} + 2>/dev/null || true; \
    fi

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    sh -ec '\
      apt_update() { \
        attempt=1; \
        while [ "$attempt" -le 5 ]; do \
          apt-get update -o Acquire::Retries=5 && return 0; \
          sleep $((attempt * 2)); \
          attempt=$((attempt + 1)); \
        done; \
        return 1; \
      }; \
      apt_update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fontconfig \
        libexpat1 \
        libfontconfig1 \
        libfreetype6 \
        libgdiplus \
        libglib2.0-0 \
        libharfbuzz0b \
        libicu72 \
        libjpeg62-turbo \
        libpng16-16 \
        libstdc++6 \
        libuuid1 \
        libx11-6 \
        libxau6 \
        libxcb1 \
        libxext6 \
        libxrender1 \
        zlib1g \
      && rm -rf /var/lib/apt/lists/*'

WORKDIR /app

RUN mkdir -p /opt/paper-agent/native /opt/paper-agent/managed /opt/paper-agent/license

RUN --mount=type=cache,target=/root/.cache/paper-agent,sharing=locked \
    sh -ec 'pkg_lower=$(printf "%s" "${SKIASHARP_NATIVE_PACKAGE}" | tr "[:upper:]" "[:lower:]"); \
    ver_lower=$(printf "%s" "${SKIASHARP_NATIVE_VERSION}" | tr "[:upper:]" "[:lower:]"); \
    cache_file="/root/.cache/paper-agent/${pkg_lower}-${ver_lower}.nupkg"; \
    url="${NUGET_FLAT_CONTAINER_BASE}/${pkg_lower}/${ver_lower}/${pkg_lower}.${ver_lower}.nupkg"; \
    python -c "import sys, zipfile; p=sys.argv[1]; zipfile.ZipFile(p).close()" "$cache_file" || rm -f "$cache_file"; \
    test -f "$cache_file" || curl -fL --retry 3 --retry-all-errors --connect-timeout 15 "$url" -o "$cache_file"; \
    python -c '\''import sys, zipfile; zf=zipfile.ZipFile(sys.argv[1]); zf.getinfo("runtimes/linux-x64/native/libSkiaSharp.so"); zf.close()'\'' "$cache_file"; \
    cp "$cache_file" /tmp/skia-native.nupkg' \
    && python -c 'from zipfile import ZipFile; from pathlib import Path; package=Path("/tmp/skia-native.nupkg"); target=Path("/opt/paper-agent/native/libSkiaSharp.so"); archive=ZipFile(package); src=archive.open("runtimes/linux-x64/native/libSkiaSharp.so"); dst=open(target, "wb"); dst.write(src.read()); dst.close(); src.close(); archive.close()' \
    && test -f /opt/paper-agent/native/libSkiaSharp.so \
    && rm -f /tmp/skia-native.nupkg

COPY custom_agents/paper/requirements-http-mcp.txt /tmp/requirements-http-mcp.txt

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python -m pip install \
      -r /tmp/requirements-http-mcp.txt

COPY custom_agents/paper /app/custom_agents/paper

RUN mkdir -p "${PAPER_SERVICE_DATA_DIR}" \
    && python --version \
    && python -c "import pythonnet; print('pythonnet ok')" \
    && dotnet --list-runtimes \
    && test -f /opt/paper-agent/native/libSkiaSharp.so \
    && ldd /opt/paper-agent/native/libSkiaSharp.so | tee /tmp/paper-agent-ldd.txt \
    && ! grep -q "not found" /tmp/paper-agent-ldd.txt

EXPOSE 8766

CMD ["python", "/app/custom_agents/paper/paper_mcp_server.py"]
