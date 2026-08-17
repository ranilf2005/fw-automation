# Cisco Secure Firewall Automation Starter Pack

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-blue.svg)](CODE_OF_CONDUCT.md)

This repository is a beginner-friendly starter kit for Cisco Secure Firewall automation with FMC-managed FTD devices.

It includes:
- Python scripts for inventory, objects, services, rules, NAT, and compliance reporting
- **Three MCP servers** that let an AI agent drive the same automation safely — see [mcp_servers/](mcp_servers/)
- Input CSV templates
- Ansible starter playbooks
- Terraform starter files
- Validation steps and test commands

> **Not a Cisco product.** Independent and community-maintained, distributed under the
> [MIT License](LICENSE). Not supported by Cisco TAC. See [NOTICE](NOTICE) and [SUPPORT.md](SUPPORT.md).

Important:
- Test in a lab or a non-production policy first.
- Some API paths and payload details vary by FMC version. Use FMC API Explorer to confirm object fields and endpoints before production use.
- Cisco documents that the FMC API uses token-based authentication, API Explorer is available on FMC, the Ansible collection uses the FMC REST API, and the Terraform provider also communicates with FMC via REST. See docs/REFERENCES.md.

## Security defaults

This kit talks to a firewall management plane, so it is configured to fail safe:

| Control | Default |
| --- | --- |
| TLS certificate verification | **Enabled** (`VERIFY_SSL=true`). Trust a private CA with `FMC_CA_BUNDLE` rather than turning it off. |
| Plaintext HTTP to FMC | Rejected |
| Credentials in git | Blocked by [.gitignore](.gitignore), pre-commit, and CI secret scanning |
| Credentials in logs | Redacted automatically |
| MCP server writes | Disabled until an explicit environment flag is set |

Read [SECURITY.md](SECURITY.md) before pointing any of this at an environment you care about.

## MCP servers for AI agents

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

## Recommended learning order
1. Inventory export
2. Object creation
3. Service object creation
4. Access rule creation
5. NAT rule creation
6. Compliance report
7. Ansible versions of the same tasks
8. Terraform for repeatable object creation
9. MCP servers, once you trust the underlying automation

## Repository layout
```text
secure-firewall-automation-starter/
├── docs/            Testing method, advanced use cases, references
├── inputs/          CSV templates (RFC 1918 sample data only)
├── outputs/         Generated reports, logs, backups (gitignored)
├── python/          Scripts and the shared common/ package
├── ansible/         Playbooks, inventory, vars
├── terraform/       Provider config and resource examples
├── mcp_servers/     Three MCP servers for AI agents
└── tests/           Unit tests (no live FMC required)
```

## 1. Install software
Install on your automation laptop or automation VM:
- Python 3.11+
- VS Code
- Git
- Postman
- Ansible
- Terraform

## 2. Create and activate Python virtual environment
### Linux/macOS
```bash
cd secure-firewall-automation-starter
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
```

### Windows PowerShell
```powershell
cd secure-firewall-automation-starter
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r python\requirements.txt
```

## 3. Configure environment
Copy the example file and update it with your FMC values.

### Linux/macOS
```bash
cp python/.env.example python/.env
```

### Windows PowerShell
```powershell
Copy-Item python\.env.example python\.env
```

Then edit `python/.env` and set:
- `FMC_HOST` — must be `https://`
- `FMC_USERNAME` — a dedicated, least-privilege API user, not a shared admin account
- `FMC_PASSWORD` — prefer exporting this in your shell over writing it to the file
- `FMC_DOMAIN_UUID` if you already know it, otherwise leave blank and discover it with the inventory script
- `VERIFY_SSL` — leave `true`. For a self-signed lab FMC, set `FMC_CA_BUNDLE` to the CA
  PEM instead of disabling verification
- `ACCESS_POLICY_ID`
- `NAT_POLICY_ID`

## 4. First tests
### 4.1 Inventory export
```bash
python python/inventory/get_inventory.py
```
Verify files were created under `outputs/reports/`.

### 4.2 Validate objects input
```bash
python python/objects/validate_objects.py inputs/objects.csv
```

### 4.3 Create objects
```bash
python python/objects/create_objects.py inputs/objects.csv
```

### 4.4 Validate services
```bash
python python/services/validate_services.py inputs/services.csv
```

### 4.5 Create service objects
```bash
python python/services/create_services.py inputs/services.csv
```

### 4.6 Validate rules
```bash
python python/policy/validate_rules.py inputs/rules.csv
```

### 4.7 Create access rules
```bash
python python/policy/create_rules.py inputs/rules.csv
```

### 4.8 Validate NAT input
```bash
python python/nat/validate_nat.py inputs/nat.csv
```

### 4.9 Create NAT rules
```bash
python python/nat/create_manual_nat.py inputs/nat.csv
```

### 4.10 Compliance report
```bash
python python/reports/compliance_report.py
```

## 5. Verification checklist for every use case
For each use case, verify in three places:
1. Script output and CSV/JSON report
2. API GET result from a follow-up script or Postman
3. FMC GUI in the correct section

For policy and NAT changes, also verify:
4. Deployment state in FMC
5. Functional behavior on the target FTD device

## 6. Ansible
Install the collection:
```bash
ansible-galaxy collection install -r ansible/requirements.yml
```

Credentials are read from the environment — `ansible/group_vars/all.yml` contains no
secrets. Export them, or supply an `ansible-vault` file:

```bash
export FMC_HOST=https://YOUR-FMC
export FMC_USERNAME=apiuser
read -rs FMC_PASSWORD && export FMC_PASSWORD

ansible-playbook -i ansible/inventory.yml ansible/playbooks/get_domain.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/get_network_objects.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/create_network_objects.yml
```

Objects created by the last playbook are defined in `ansible/vars/network_objects.yml`,
not inline in the playbook.

## 7. Terraform
Terraform resource support depends on FMC version. Start with provider init and use a single object resource only after confirming the exact resource names your provider version supports.

Supply credentials through environment variables so nothing lands on disk:

```bash
cd terraform
export TF_VAR_fmc_url=https://YOUR-FMC
export TF_VAR_fmc_username=apiuser
read -rs TF_VAR_fmc_password && export TF_VAR_fmc_password

terraform init
terraform validate
terraform plan
```

`terraform.tfstate` records object values in cleartext and is gitignored. Use an
encrypted remote backend for anything beyond a local lab.

## 8. Rollback approach
- Objects: delete only the newly created test objects
- Rules: delete the newly created test rules, then deploy
- NAT: delete the newly created NAT rules, then deploy
- Reports: no rollback needed because read-only

## 9. Known limits of this starter pack
- Deployment APIs differ across versions and workflows; use API Explorer to confirm deploy task payloads in your FMC version.
- VPN and device onboarding vary more by release and design, so they are documented as guided steps in `docs/ADVANCED_USE_CASES.md` rather than fully coded here.
- Terraform resource names and supported resources depend on provider and FMC version.

## 10. Development

```bash
pip install -r python/requirements.txt
pip install -r requirements-dev.txt
pre-commit install
```

Run the same checks CI runs:

```bash
ruff check .            # lint
ruff format --check .   # formatting
pytest                  # unit tests, no live FMC needed
bandit -c pyproject.toml -r python mcp_servers
ansible-lint ansible/
terraform -chdir=terraform fmt -check
```

Every pull request runs lint, type checking, unit tests, `bandit`, `pip-audit`,
`gitleaks`, and CodeQL. See [.github/workflows/ci.yml](../.github/workflows/ci.yml).

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
