# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `-h` / `--help` on every `python/` script via a shared `python/common/cli.py` helper.
  Help output documents the arguments and the required environment variables, and a
  missing input CSV now fails immediately with a clear message and exit code 2.
- `--log-level` flag to override `LOG_LEVEL` for a single run.

### Changed

- Restructured the repository README and all three MCP server READMEs onto the official
  [Cisco Code Exchange documentation template](https://github.com/CiscoDevNet/code-exchange-repo-template):
  full use-case titles, and `Use Case`, `Installation`, `Configuration`, `Usage`,
  `Related Sandbox`, `Known issues`, `Getting help`, `Getting involved`,
  `Credits and references`, and `Licensing info` sections.
- Installation sections now list prerequisites with download links and cover Windows,
  macOS, and Linux.
- `mcp_servers/SUBMISSION.md` rewritten against the live Code Exchange submission
  requirements, including a comparison of MIT against the Cisco Sample Code License and a
  status check against Cisco's published good and bad practices.

## [1.0.0] - 2026-08-17

First release hardened for public consumption.

### Added

- **`mcp_servers/`** — three Model Context Protocol servers that let an AI agent drive
  Cisco Secure Firewall automation safely:
  - `mcp_servers/rest-api-mcp/` — direct FMC REST API tools (inventory, objects,
    services, rules, NAT, change preview) with a dry-run gate on every write.
  - `mcp_servers/ansible-mcp/` — allowlisted `cisco.fmcansible` playbook execution with
    syntax check and `--check` dry run.
  - `mcp_servers/terraform-mcp/` — `init`/`validate`/`plan`/`show` with structured plan
    summarisation and drift detection. `apply` is disabled by default.
  - Each server ships a README, a Code Exchange submission article (`article.html`),
    submission metadata, `.env.example`, Dockerfile, compose file, interactive client,
    and unit tests.
- Governance and compliance baseline: `LICENSE` (MIT), `NOTICE`, `CODE_OF_CONDUCT.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `CHANGELOG.md`.
- GitHub automation: CI (ruff, mypy, bandit, pytest, ansible-lint, terraform fmt/validate),
  CodeQL, gitleaks secret scanning, pip-audit, Dependabot, issue and PR templates.
- Tooling config: `pyproject.toml` (ruff/mypy/bandit/pytest), `.pre-commit-config.yaml`,
  `.editorconfig`, `requirements-dev.txt`.
- Unit test suite under `tests/` that runs without a live FMC.
- `FMC_CA_BUNDLE` support so a private CA can be trusted instead of disabling TLS
  verification.
- SPDX license headers on all source files.

### Changed

- **Breaking:** TLS certificate verification now defaults to **enabled**
  (`VERIFY_SSL=true`, `fmc_verify_ssl: true`). Lab users with self-signed certificates
  must now opt out explicitly.
- Pinned all Python dependencies with compatible-release (`~=`) constraints.
- Pinned the Terraform `CiscoDevNet/fmc` provider to a supported major version.
- `ansible/group_vars/all.yml` no longer carries inline plaintext credentials; it reads
  from environment variables or an `ansible-vault` file.
- `ansible/playbooks/create_network_objects.yml` reads its payload from
  `ansible/vars/network_objects.yml` instead of a hardcoded inline object.
- Replaced broad `except Exception` handlers with specific exception types across all
  `create_*.py` scripts.
- Credentials, tokens, and `Authorization` headers are now redacted from logs.

### Fixed

- `python/nat/create_manual_nat.py` raised an unhandled `KeyError` when a CSV row
  referenced a network object that did not exist in FMC; it now reports the missing
  object name and skips the row.
- Compiled Python bytecode (`__pycache__/*.pyc`) is no longer tracked in git.

### Security

- TLS verification on by default (see Changed).
- Secret scanning, dependency auditing, and static analysis enforced in CI.
- Documented least-privilege API user guidance and credential handling in
  [SECURITY.md](SECURITY.md).

[Unreleased]: https://github.com/ranilf2005/fw-automation/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ranilf2005/fw-automation/releases/tag/v1.0.0
