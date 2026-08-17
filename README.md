# Secure Firewall Automation Starter Pack, automates objects, rules, NAT, and compliance reporting on FMC-managed FTD using Python, Ansible, Terraform, and MCP servers for AI agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-blue.svg)](CODE_OF_CONDUCT.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Firewall change work is repetitive, error-prone, and hard to audit: an engineer reads a
ticket, hand-creates objects in the FMC GUI, writes a rule, hopes nothing shadows it, and
leaves no machine-readable record of what happened. This starter pack replaces that loop
with reviewed automation. It takes CSV input, validates it **before** anything is sent to
the firewall, creates network objects, service objects, access rules, and NAT rules
through the Cisco Secure Firewall Management Center (FMC) REST API, and produces
compliance and inventory reports you can attach to a change record.

It teaches the same six tasks three ways — Python, Ansible, and Terraform — so you can
see how imperative, procedural, and declarative automation differ against the same
device, and then adopt whichever matches how your team already works. It also ships
**three Model Context Protocol (MCP) servers** so an AI agent can drive that automation
without being able to change a firewall in a single unreviewed step.

**Technology stack:** Python 3.11+ (`requests`, `pandas`), Ansible with the
`cisco.fmcansible` collection, Terraform with the `CiscoDevNet/fmc` provider, and
[FastMCP](https://github.com/jlowin/fastmcp) for the MCP servers. Standalone — no
framework required. Docker images provided for the MCP servers.

**Status:** 1.0.0. Lab-ready and CI-tested (193 unit tests, no live FMC required). Treat
the write paths as beta until you have validated the payloads against your own FMC
version.

> **Not a Cisco product.** Independent and community-maintained, distributed under the
> [MIT License](LICENSE). Not supported by Cisco TAC. See [NOTICE](NOTICE) and
> [SUPPORT.md](SUPPORT.md).

## Use Case

A mid-size enterprise runs FMC-managed FTD firewalls and processes 20–40 firewall change
requests a month. Each one is done by hand. The problems that creates:

- **No pre-flight validation.** A typo in a subnet mask is discovered by FMC, halfway
  through the change window.
- **Object sprawl.** The same subnet exists five times under five names, because nobody
  can search for "which object already covers 10.10.20.0/24".
- **Unsafe deletions.** Nobody knows which rules reference an object, so stale objects
  are never cleaned up.
- **Weak audit trail.** The change record says "added rule per CHG12345"; reconstructing
  what actually changed means reading the FMC audit log.
- **Inconsistent hygiene.** Some rules log, some do not. Some have comments, some do not.

This repository addresses each of those:

| Problem | What this provides | Outcome |
| --- | --- | --- |
| No pre-flight validation | `validate_*.py` scripts check every CSV row — column presence, IP/CIDR correctness, port ranges, duplicate names, and whether referenced zones and objects actually exist in FMC | Bad input fails in seconds, at your desk, not in the change window |
| Object sprawl | `search_objects` with IP-containment matching, and duplicate-value detection in `compliance_report.py` | Find the object that already covers an address before creating a sixth one |
| Unsafe deletions | `find_object_usage` returns every access rule referencing an object plus a `safe_to_delete` flag | Clean up stale objects with evidence |
| Weak audit trail | Every run writes a per-row CSV result to `outputs/reports/` with CREATED / SKIP / FAILED and a reason | Attach a machine-readable record to the change ticket |
| Inconsistent hygiene | `compliance_report.py` flags naming-convention breaches, duplicate values, rules without `logEnd`, and rules without comments | Measurable policy hygiene instead of opinion |

**Challenges overcome.** FMC payload schemas vary between releases, so every write script
documents which endpoint it uses and tells you to confirm it in API Explorer. FMC
paginates and silently truncates large object lists, so the shared client implements
`get_all()` to follow pagination rather than passing `limit=1000` and hoping. Manual NAT
payloads differ most across versions, so that script is explicitly marked as
version-sensitive.

**Where it could go next.** Wiring the MCP servers to an ITSM system so a change ticket
produces the plan automatically, and extending the compliance report to shadowed-rule and
hit-count analysis. See [mcp_servers/IDEAS.md](mcp_servers/IDEAS.md).

### Security defaults

This kit talks to a firewall management plane, so it is configured to fail safe:

| Control | Default |
| --- | --- |
| TLS certificate verification | **Enabled** (`VERIFY_SSL=true`). Trust a private CA with `FMC_CA_BUNDLE` rather than turning it off. |
| Plaintext HTTP to FMC | Rejected |
| Credentials in source files | None. All credentials come from the environment or an `ansible-vault` file |
| Credentials in git | Blocked by [.gitignore](.gitignore), pre-commit hooks, and CI secret scanning |
| Credentials in logs | Redacted automatically |
| MCP server writes | Disabled until an explicit environment flag is set |

Read [SECURITY.md](SECURITY.md) before pointing any of this at an environment you care
about.

### MCP servers for AI agents

[mcp_servers/](mcp_servers/) contains three independently deployable Model Context
Protocol servers, one per automation style:

| Server | What an agent gets |
| --- | --- |
| [rest-api-mcp](mcp_servers/rest-api-mcp/) | FMC REST tooling: inventory, object search with IP containment, object-usage tracing, rule listing, and a preview → confirm → apply change pipeline |
| [ansible-mcp](mcp_servers/ansible-mcp/) | Allowlisted `cisco.fmcansible` playbooks with syntax check, `--check` dry run, and gated execution |
| [terraform-mcp](mcp_servers/terraform-mcp/) | `init` / `validate` / `plan` / `explain` / drift detection, with `apply` off by default |

All three are **read-only by default**, split every mutation into a preview and an apply
half bound by a signed confirmation token, and redact secrets before anything reaches a
model. See [mcp_servers/README.md](mcp_servers/README.md).

### Repository layout

```text
fw-automation/
├── docs/            Testing method, advanced use cases, references
├── inputs/          CSV templates (RFC 1918 sample data only)
├── outputs/         Generated reports, logs, backups (gitignored)
├── python/          Scripts and the shared common/ package
├── ansible/         Playbooks, inventory, vars
├── terraform/       Provider config and resource examples
├── mcp_servers/     Three MCP servers for AI agents
└── tests/           Unit tests (no live FMC required)
```

### Recommended learning order

1. Inventory export
2. Object creation
3. Service object creation
4. Access rule creation
5. NAT rule creation
6. Compliance report
7. Ansible versions of the same tasks
8. Terraform for repeatable object creation
9. MCP servers, once you trust the underlying automation

## Installation

### Prerequisites

| Requirement | Version | Where to get it |
| --- | --- | --- |
| Python | 3.11 or later | <https://www.python.org/downloads/> |
| Git | any recent | <https://git-scm.com/downloads> |
| Ansible (optional) | ansible-core 2.17+ | <https://docs.ansible.com/ansible/latest/installation_guide/index.html> |
| Terraform (optional) | 1.6 or later | <https://developer.hashicorp.com/terraform/install> |
| Docker (optional, for the MCP servers) | any recent | <https://docs.docker.com/get-docker/> |
| An FMC | 7.0+ with REST API enabled | Your lab, or a [DevNet Sandbox](#related-sandbox) |

You also need a **dedicated FMC API user** with least privilege. Do not use a shared
administrator account.

### Clone the repository

```bash
git clone https://github.com/ranilf2005/fw-automation.git
cd fw-automation
```

### Set up a Python virtual environment

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
```

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r python\requirements.txt
```

**Windows Command Prompt**

```bat
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r python\requirements.txt
```

### Verify the install

This runs the unit tests, which need no FMC and no credentials:

```bash
pip install -r requirements-dev.txt
pytest
```

You should see all tests pass. If they do, your Python environment is correct and any
later failure is a configuration or connectivity problem, not an install problem.

## Configuration

All configuration is environment based. **No credential is ever stored in a source file.**

### Python scripts

Copy the template:

**Linux / macOS**

```bash
cp python/.env.example python/.env
```

**Windows PowerShell**

```powershell
Copy-Item python\.env.example python\.env
```

Then edit `python/.env`:

| Variable | Required | Format | Notes |
| --- | --- | --- | --- |
| `FMC_HOST` | yes | `https://host-or-ip` — scheme included, **no trailing slash**, no path | Plaintext `http://` is rejected |
| `FMC_USERNAME` | yes | plain string | A dedicated least-privilege API user |
| `FMC_PASSWORD` | yes | plain string | Prefer exporting it in your shell over writing it to the file |
| `VERIFY_SSL` | no | `true` / `false` | Defaults to `true`. Leave it on |
| `FMC_CA_BUNDLE` | no | absolute path to a PEM file | The correct way to handle a self-signed lab FMC |
| `FMC_DOMAIN_UUID` | no | UUID | Leave blank to auto-discover the global domain |
| `ACCESS_POLICY_ID` | for rule scripts | UUID | Get it from `outputs/reports/access_policies.json` |
| `NAT_POLICY_ID` | for NAT scripts | UUID | From FMC |
| `LOG_LEVEL` | no | `DEBUG`/`INFO`/`WARNING`/`ERROR` | Defaults to `INFO` |

`FMC_HOST` format matters: write `https://fmc.example.local`, **not** `fmc.example.local`
and **not** `https://fmc.example.local/`.

To keep the password off disk entirely, leave `FMC_PASSWORD` blank in the file and export
it instead:

```bash
read -rs FMC_PASSWORD && export FMC_PASSWORD     # Linux/macOS
```

```powershell
$env:FMC_PASSWORD = Read-Host -AsSecureString | ConvertFrom-SecureString -AsPlainText  # PowerShell 7+
```

### Ansible

`ansible/group_vars/all.yml` contains **no secrets** — it reads the same environment
variables. Alternatively supply an `ansible-vault` file:

```bash
ansible-vault create ansible/vars/vault.yml     # add: fmc_password: "..."
```

### Terraform

Supply credentials as `TF_VAR_*` environment variables so nothing lands on disk. See
[terraform/terraform.tfvars.example](terraform/terraform.tfvars.example) for the
non-secret settings.

### MCP servers

Each server has its own `.env.example`. See the per-server README.

## Usage

Every script supports `--help`, which documents its arguments and the environment
variables it needs:

```bash
python python/objects/validate_objects.py --help
```

```text
usage: validate_objects.py [-h] [--log-level {DEBUG,INFO,WARNING,ERROR}] [input]

Validate an object CSV before anything is sent to FMC.

positional arguments:
  input                 Path to the input CSV. Defaults to inputs/objects.csv

options:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Override LOG_LEVEL for this run.
```

The `input` argument is optional — omit it and the script uses the matching sample in
`inputs/`. A path that does not exist is reported immediately with exit code 2. Run the
steps in the order below; each `validate_*` step is read-only and safe.

> **Always run the `validate_*` script first.** It is the only step that catches a bad
> CSV before FMC sees it.

### Read-only: export your inventory

```bash
python python/inventory/get_inventory.py
```

Writes `domains.json`, `devices.json`, `network_objects.json`, `host_objects.json`,
`security_zones.json`, and `access_policies.json` to `outputs/reports/`. Open
`access_policies.json` to find the `id` you need for `ACCESS_POLICY_ID`.

### Network and host objects

```bash
python python/objects/validate_objects.py inputs/objects.csv
python python/objects/create_objects.py   inputs/objects.csv
```

`inputs/objects.csv` format:

```csv
name,type,value,description
APP1_HOST,Host,10.10.10.10,Application host
APP1_NET,Network,10.10.20.0/24,Application subnet
```

`type` is `Host` or `Network`. `value` is a bare IP for `Host` and CIDR for `Network`.
Objects that already exist by name are reported as `SKIP`, not overwritten.

### Service objects

```bash
python python/services/validate_services.py inputs/services.csv
python python/services/create_services.py   inputs/services.csv
```

```csv
name,protocol,port,description
HTTPS_TCP,TCP,443,HTTPS
```

`protocol` is `TCP` or `UDP`. `port` is 1–65535.

### Access rules

Requires `ACCESS_POLICY_ID` in `python/.env`.

```bash
python python/policy/validate_rules.py inputs/rules.csv
python python/policy/create_rules.py   inputs/rules.csv
python python/policy/get_rules.py                        # read back what exists
```

```csv
rule_name,src_zones,dst_zones,src_networks,dst_networks,service_objects,action,enabled,log_begin,log_end,comment
ALLOW_APP1_DB,inside,server,APP1_HOST,DB1_HOST,MYSQL_TCP,ALLOW,true,false,true,Approved CHG12345
```

Multiple zones, networks, or services in one field are **semicolon separated**:
`inside;dmz`. `action` is `ALLOW`, `BLOCK`, `TRUST`, or `MONITOR`. A row referencing an
object that does not exist in FMC is reported as `SKIP` with the missing name — it does
not abort the run.

### NAT rules

Requires `NAT_POLICY_ID`. Manual NAT payloads vary most between FMC releases — confirm
yours in API Explorer first.

```bash
python python/nat/validate_nat.py       inputs/nat.csv
python python/nat/create_manual_nat.py  inputs/nat.csv
```

### Compliance report

```bash
python python/reports/compliance_report.py
```

Writes `outputs/reports/compliance_report.csv` flagging naming-convention breaches,
duplicate object values, rules without `logEnd`, and rules without comments.

### Ansible

```bash
ansible-galaxy collection install -r ansible/requirements.yml

export FMC_HOST=https://fmc.example.local
export FMC_USERNAME=apiuser
read -rs FMC_PASSWORD && export FMC_PASSWORD

ansible-playbook -i ansible/inventory.yml ansible/playbooks/get_domain.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/get_network_objects.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/create_network_objects.yml
```

Objects created by the last playbook are defined in `ansible/vars/network_objects.yml`,
not inline in the playbook — edit that file, not the playbook.

### Terraform

```bash
cd terraform
export TF_VAR_fmc_url=https://fmc.example.local
export TF_VAR_fmc_username=apiuser
read -rs TF_VAR_fmc_password && export TF_VAR_fmc_password

terraform init
terraform validate
terraform plan          # review every change before applying
```

Resource names depend on your provider version. Confirm them first:

```bash
terraform providers schema -json | jq '.provider_schemas[].resource_schemas | keys'
```

`terraform.tfstate` records object values in cleartext and is gitignored. Use an
encrypted remote backend for anything beyond a local lab.

### MCP servers

```bash
cd mcp_servers/rest-api-mcp        # or ansible-mcp / terraform-mcp
pip install -r requirements.txt
cp .env.example .env
python client/test_client.py       # interactive smoke test
```

Or with Docker:

```bash
docker compose up -d --build
```

Each server's README has a ready-to-paste `mcpServers` client configuration block for
Claude Desktop, VS Code, Cursor, and other MCP-aware agents.

### Verification checklist for every use case

For each use case, verify in three places:

1. Script output and the CSV/JSON report in `outputs/reports/`
2. API `GET` result from a follow-up script or Postman
3. FMC GUI in the correct section

For policy and NAT changes, also verify:

4. Deployment state in FMC
5. Functional behaviour on the target FTD device

See [docs/TESTING.md](docs/TESTING.md) for the full method.

### Rollback

- **Objects:** delete only the newly created test objects
- **Rules:** delete the newly created test rules, then deploy
- **NAT:** delete the newly created NAT rules, then deploy
- **Reports:** no rollback needed, they are read-only

## Related Sandbox

You need an FMC to run this against. If you do not have a lab, Cisco DevNet provides free
sandboxes:

- [DevNet Sandbox catalogue](https://devnetsandbox.cisco.com/RM/Topology) — search for
  **Secure Firewall** or **Firepower**; both always-on and reservable options exist
- [Cisco Secure Firewall developer centre](https://developer.cisco.com/secure-firewall/) —
  API documentation and getting-started material

Once you have a sandbox, set `FMC_HOST`, `FMC_USERNAME`, and `FMC_PASSWORD` to the
sandbox values. Sandbox FMCs normally present a self-signed certificate — download its CA
and set `FMC_CA_BUNDLE` rather than setting `VERIFY_SSL=false`.

Start with `python python/inventory/get_inventory.py`. If that writes files to
`outputs/reports/`, your connectivity and credentials are correct.

## Known issues

- **FMC payload schemas vary by release.** This is the single most common source of
  failures. Confirm every endpoint and field in **API Explorer** on your own FMC
  (`https://<fmc-host>/api/api-explorer`) before relying on a write path.
- **Manual NAT is the most version-sensitive script.** `create_manual_nat.py` builds an
  `FTDManualNatRule` payload whose accepted fields differ noticeably between releases.
- **No deployment trigger.** These scripts change the FMC configuration but never deploy
  it to devices. Deploy from FMC after reviewing.
- **VPN and device onboarding are not coded.** They vary too much by release and design;
  see [docs/ADVANCED_USE_CASES.md](docs/ADVANCED_USE_CASES.md) for guided steps.
- **Terraform resources depend on the provider version.** `terraform/main.tf` ships with
  the example resource commented out on purpose.
- **Rate limiting.** FMC limits API requests per session. Very large CSVs may need to be
  split.

Issues are tracked in
[GitHub Issues](https://github.com/ranilf2005/fw-automation/issues). Please use the
provided templates and include your FMC version.

## Getting help

| I need... | Go to |
| --- | --- |
| Help with this repo, a bug, or a feature idea | [GitHub Issues](https://github.com/ranilf2005/fw-automation/issues/new/choose) |
| To report a security vulnerability **in this repo** | [SECURITY.md](SECURITY.md) — do **not** open a public issue |
| Help with Cisco Secure Firewall itself | [Cisco TAC](https://www.cisco.com/c/en/us/support/index.html) |
| A vulnerability in a Cisco product | [Cisco PSIRT](https://www.cisco.com/c/en/us/about/security-center/security-vulnerability-policy.html) |
| FMC REST API questions | [Cisco DevNet Secure Firewall](https://developer.cisco.com/secure-firewall/) |
| Community discussion | [Cisco Code Exchange Community](https://community.cisco.com/t5/code-exchange/bd-p/dev-code-exchange) |

Before opening an issue, re-run with `LOG_LEVEL=DEBUG` and confirm the endpoint in API
Explorer. Full guidance is in [SUPPORT.md](SUPPORT.md).

## Getting involved

Contributions are welcome. This project is judged on **clarity and safety** as much as
functionality, because the code talks to a firewall.

Current focus areas where help is most useful:

- Validating the write paths against more FMC versions and reporting payload differences
- Extending `compliance_report.py` with shadowed-rule and hit-count analysis
- Object groups, ranges, and FQDN objects in the REST MCP server
- Additional MCP server concepts from [mcp_servers/IDEAS.md](mcp_servers/IDEAS.md)

Development environment (differs from the general install by adding the dev tooling):

```bash
pip install -r python/requirements.txt
pip install -r requirements-dev.txt
pre-commit install
```

Run the same checks CI runs:

```bash
ruff check .            # lint
ruff format --check .   # formatting
pytest                  # 193 unit tests, no live FMC needed
bandit -c pyproject.toml -r python mcp_servers
ansible-lint ansible/
terraform -chdir=terraform fmt -check
```

Every pull request additionally runs `mypy`, `pip-audit`, `gitleaks`, CodeQL, and OSSF
Scorecard. See [.github/workflows/ci.yml](.github/workflows/ci.yml).

Full instructions on *how* to contribute are in [CONTRIBUTING.md](CONTRIBUTING.md), and
all participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Credits and references

**Projects that inspired this**

- [CiscoDevNet/CiscoFMC-MCP-server-community](https://github.com/CiscoDevNet/CiscoFMC-MCP-server-community) —
  the published FMC MCP server whose structure and safety posture the servers here follow
- [CiscoDevNet/code-exchange-repo-template](https://github.com/CiscoDevNet/code-exchange-repo-template) —
  the documentation template this README follows

**Related projects**

- [CiscoDevNet/FMCAnsible](https://github.com/CiscoDevNet/FMCAnsible) — the
  `cisco.fmcansible` collection (GPL-3.0)
- [CiscoDevNet/terraform-provider-fmc](https://github.com/CiscoDevNet/terraform-provider-fmc) —
  the Terraform `fmc` provider (MPL-2.0)
- [CiscoDevNet/secure-firewall](https://github.com/CiscoDevNet/secure-firewall) —
  Cisco's own templates and automation resources

**References**

- [Cisco Secure Firewall Management Center REST API Quick Start Guide](https://www.cisco.com/c/en/us/td/docs/security/firepower/latest/api/REST/secure_firewall_management_center_rest_api_quick_start_guide.html)
- [Model Context Protocol specification](https://modelcontextprotocol.io)
- Additional links in [docs/REFERENCES.md](docs/REFERENCES.md)

## Licensing info

This code is licensed under the MIT License. See [LICENSE](LICENSE) for details.

Third-party attribution, Cisco trademark acknowledgement, and the generative-AI
disclosure are in [NOTICE](NOTICE). Note in particular that the `cisco.fmcansible`
collection is GPL-3.0-or-later, the Terraform `fmc` provider is MPL-2.0, and the
Terraform CLI is BUSL-1.1 — all are *invoked* by this project, never vendored or
redistributed, so no copyleft obligation attaches to this MIT-licensed code.

## Project documents

| Document | Purpose |
| --- | --- |
| [LICENSE](LICENSE) | MIT licence |
| [NOTICE](NOTICE) | Trademarks, third-party licences, AI disclosure |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting and credential guidance |
| [SUPPORT.md](SUPPORT.md) | Where to get help — and where not to |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Contributor Covenant 2.1 |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [docs/TESTING.md](docs/TESTING.md) | Validation method for every use case |
| [docs/ADVANCED_USE_CASES.md](docs/ADVANCED_USE_CASES.md) | VPN and device onboarding guidance |
| [docs/REFERENCES.md](docs/REFERENCES.md) | External documentation links |
