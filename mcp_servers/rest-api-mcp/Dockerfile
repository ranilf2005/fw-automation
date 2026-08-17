# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
FROM python:3.12-slim AS base

# Do not run as root.
RUN groupadd --gid 10001 mcp \
    && useradd --uid 10001 --gid mcp --create-home --shell /usr/sbin/nologin mcp

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY sfw_mcp_rest/ ./sfw_mcp_rest/
COPY client/ ./client/

USER mcp

# HTTP transport is the norm in a container.
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    FMC_VERIFY_SSL=true \
    FMC_ALLOW_WRITES=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket,os,sys; s=socket.create_connection(('127.0.0.1', int(os.environ.get('MCP_PORT','8000'))), 3); s.close()" || exit 1

ENTRYPOINT ["python", "-m", "sfw_mcp_rest"]
