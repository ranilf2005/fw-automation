# Contributing

Thanks for your interest in improving this starter kit. This project exists to help
people learn Cisco Secure Firewall automation safely, so contributions are judged on
clarity and safety as much as on functionality.

## Ground rules

1. **No real environment data.** No production IP addresses, hostnames, FQDNs,
   serial numbers, policy names, usernames, tokens, or certificates. Use
   [RFC 1918](https://datatracker.ietf.org/doc/html/rfc1918) addressing
   (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`),
   [RFC 5737](https://datatracker.ietf.org/doc/html/rfc5737) documentation prefixes
   (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), and `.example`/`.invalid`
   domains.
2. **Secure by default.** New code must default to TLS verification on, read-only
   behaviour, and least privilege. Anything destructive is opt-in and logged.
3. **Lab first.** Anything that writes to FMC must be documented with a validation
   step and a rollback step.
4. **You own your contribution.** By submitting a pull request you certify that you
   wrote the code or have the right to submit it, and you license it under the
   repository's [MIT License](LICENSE). Do not paste in code from sources with
   incompatible licenses.

## Getting set up

```bash
git clone https://github.com/ranilf2005/fw-automation.git
cd fw-automation/secure-firewall-automation-starter

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

pip install -r python/requirements.txt
pip install -r requirements-dev.txt
pre-commit install
```

## Before you open a pull request

Run the same checks CI runs:

```bash
ruff check .                 # lint
ruff format --check .        # formatting
mypy python mcp_servers      # type checking
bandit -c pyproject.toml -r python mcp_servers   # security static analysis
pytest                       # unit tests
```

Or in one shot:

```bash
pre-commit run --all-files && pytest
```

For Ansible and Terraform changes:

```bash
ansible-lint ansible/
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
```

## Coding standards

- Python 3.11+. Start every module with `from __future__ import annotations`.
- Full type hints on public functions. PEP 604 unions (`str | None`).
- Reuse the shared helpers in `python/common/` — `FMCClient`, `get_logger`,
  `load_settings`, `write_json`, `write_csv`. Do not create a second HTTP client.
- Log through `get_logger(__name__)`. Never log credentials, tokens, or full
  `Authorization` headers.
- Catch specific exceptions (`requests.RequestException`, `ValueError`, `KeyError`),
  not bare `Exception`.
- Every source file carries the SPDX header:

  ```python
  # SPDX-License-Identifier: MIT
  # Copyright (c) 2026 secure-firewall-automation-starter contributors
  ```

- New behaviour needs a unit test in `tests/`. Tests must not require a live FMC —
  mock the HTTP layer.

## Commit and PR conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(objects): add bulk network group creation
fix(nat): raise a clear error when a referenced object is missing
docs(mcp): document read-only defaults
chore(deps): pin requests to 2.32.3
```

Pull requests should:

- Target `main` from a topic branch
- Describe what changed, why, and how you tested it
- Note whether the change was validated against a lab FMC, and which version
- Update `CHANGELOG.md` under `## [Unreleased]`
- Stay focused; unrelated refactors belong in separate PRs

## Reporting bugs and requesting features

Use the [issue templates](https://github.com/ranilf2005/fw-automation/issues/new/choose).
Always include your FMC version and, where relevant, the exact API path used — FMC
payload schemas vary by release, which is the single most common source of
"it works for me" problems here.

For security issues, follow [SECURITY.md](SECURITY.md) instead of opening an issue.
