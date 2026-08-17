# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-17

First public release, hardened and documented for Cisco DevNet Code Exchange.

### Added

- `-h` / `--help` on every `python/` script via a shared `python/common/cli.py` helper.
  Help output documents the arguments and the required environment variables, and a
  missing input CSV now fails immediately with a clear message and exit code 2.
- `--log-level` flag to override `LOG_LEVEL` for a single run.
- OSSF Scorecard workflow ([.github/workflows/scorecard.yml](.github/workflows/scorecard.yml)),
  closing Cisco Code Exchange good practice #12.
- Container build job in CI that builds all three MCP server images, so the Dockerfiles
  are covered by the same pipeline as the Python code.
- Illustrative architecture, agent-session, and change-gate diagrams under
  `docs/images/`, referenced from the READMEs.

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
- The project lives at the **repository root**, because Cisco Code Exchange renders the
  root `README.md` and reads the root `LICENSE`.
- Copyright holder set to `Ranil Fernando` in `LICENSE` and all SPDX headers.
- The repository README and all three MCP server READMEs follow the official
  [Cisco Code Exchange documentation template](https://github.com/CiscoDevNet/code-exchange-repo-template):
  full use-case titles, and `Use Case`, `Installation`, `Configuration`, `Usage`,
  `Related Sandbox`, `Known issues`, `Getting help`, `Getting involved`,
  `Credits and references`, and `Licensing info` sections. Installation sections list
  prerequisites with download links and cover Windows, macOS, and Linux.
- `mcp_servers/SUBMISSION.md` written against the live Code Exchange submission
  requirements, including a comparison of MIT against the Cisco Sample Code License and
  a status check against Cisco's published good and bad practices.
- The Ansible MCP server now requires Python 3.12 or later, following its `ansible-core`
  2.21 dependency.
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

- The CI workflow had never completed a successful run.
  `mcp_servers/rest-api-mcp/requirements.txt` was unsatisfiable on its own
  (`httpx~=0.27.2` against `fastmcp`'s `httpx>=0.28.1`), and the unskippable
  `syntax-check` rule was listed in the ansible-lint `skip_list`. Both are resolved and
  every job now passes.
- Four type errors that the never-executed mypy step had been masking: duplicate
  `client/test_client.py` modules, an `IPv4Network | IPv6Network` union passed to
  `subnet_of()`, and two variables reused with a second, incompatible type.
- `python/nat/create_manual_nat.py` raised an unhandled `KeyError` when a CSV row
  referenced a network object that did not exist in FMC; it now reports the missing
  object name and skips the row.
- Compiled Python bytecode (`__pycache__/*.pyc`) is no longer tracked in git.

### Security

- TLS verification on by default (see Changed).
- Secret scanning, dependency auditing, and static analysis enforced in CI.
- Cleared every finding `pip-audit --strict` reported across all four requirements
  files, which required moving `fastmcp` to the 3.x line and raising `requests`,
  `python-dotenv`, and `ansible-core`.
- Documented least-privilege API user guidance and credential handling in
  [SECURITY.md](SECURITY.md).

[1.0.0]: https://github.com/ranilf2005/fw-automation/releases/tag/v1.0.0
