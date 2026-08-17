# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
FROM python:3.12-slim AS base

RUN groupadd --gid 10001 mcp \
    && useradd --uid 10001 --gid mcp --create-home --shell /usr/sbin/nologin mcp

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The FMC Ansible collection is GPL-3.0-or-later and is installed from Ansible Galaxy
# at build time, not vendored into this image's source. See the repository NOTICE.
COPY ansible-requirements.yml ./
RUN ansible-galaxy collection install -r ansible-requirements.yml -p /usr/share/ansible/collections

COPY sfw_mcp_ansible/ ./sfw_mcp_ansible/
COPY client/ ./client/

USER mcp

ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8001 \
    ANSIBLE_COLLECTIONS_PATH=/usr/share/ansible/collections \
    ANSIBLE_MCP_ALLOW_RUN=false \
    VERIFY_SSL=true

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket,os,sys; s=socket.create_connection(('127.0.0.1', int(os.environ.get('MCP_PORT','8001'))), 3); s.close()" || exit 1

ENTRYPOINT ["python", "-m", "sfw_mcp_ansible"]
