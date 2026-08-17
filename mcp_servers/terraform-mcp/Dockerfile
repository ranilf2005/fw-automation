# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
FROM hashicorp/terraform:1.15.8 AS terraform

FROM python:3.14-slim AS base

# Terraform is licensed BUSL-1.1 by HashiCorp. The binary is copied from the official
# image at build time and is not redistributed by this project. See the NOTICE file.
COPY --from=terraform /bin/terraform /usr/local/bin/terraform

RUN groupadd --gid 10001 mcp \
    && useradd --uid 10001 --gid mcp --create-home --shell /usr/sbin/nologin mcp

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY sfw_mcp_terraform/ ./sfw_mcp_terraform/
COPY client/ ./client/

USER mcp

ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8002 \
    TF_MCP_ALLOW_APPLY=false \
    TF_IN_AUTOMATION=1 \
    TF_INPUT=0 \
    CHECKPOINT_DISABLE=1

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket,os,sys; s=socket.create_connection(('127.0.0.1', int(os.environ.get('MCP_PORT','8002'))), 3); s.close()" || exit 1

ENTRYPOINT ["python", "-m", "sfw_mcp_terraform"]
