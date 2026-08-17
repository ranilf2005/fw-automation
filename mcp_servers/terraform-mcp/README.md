# Terraform MCP Server for Cisco Secure Firewall, lets an AI agent explain Terraform plans and detect configuration drift on FMC without being able to apply

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Terraform 1.6+](https://img.shields.io/badge/terraform-1.6%2B-purple.svg)](https://developer.hashicorp.com/terraform/install)
[![MCP](https://img.shields.io/badge/MCP-stdio%20%7C%20HTTP-green.svg)](https://modelcontextprotocol.io)

`terraform plan` output is dense and very easy to skim past — which is exactly how a
destructive change reaches production. Turning that output into *"this deletes two rules
and replaces the object three rules depend on"* is precisely what a language model is
good at, and it is a **read-only** operation. This Model Context Protocol server gives an
AI agent the Terraform workflow for Cisco Secure Firewall: validate, plan, explain, and
detect drift, all read-only, with `apply` disabled by default and gated behind a
plan-bound confirmation token.

**Technology stack:** Python 3.11+, [FastMCP](https://github.com/jlowin/fastmcp), and the
Terraform CLI with the `CiscoDevNet/fmc` provider. Standalone server, speaks MCP over
stdio or HTTP. Docker image provided.

**Status:** 1.0.0. The read-only tools are the point of this server and are stable; treat
`apply_plan` as beta.

**Read-only tools**

- `list_workspaces` — the Terraform directories this server may operate on.
- `get_versions` — Terraform CLI and provider versions.
- `init_workspace` — `terraform init -backend=false`.
- `validate_workspace` — `terraform validate -json`, returning structured diagnostics.
- `plan_workspace` — plan to a file, return a compact **sanitised** change summary plus a
  confirmation token.
- `explain_plan` — re-read the saved plan resource by resource, with a plain-language
  narrative.
- `detect_drift` — refresh-only plan: what changed outside Terraform.
- `show_state` — sanitised state summary.

**Write tool (disabled by default)**

- `apply_plan` — apply the **saved plan file**, so what runs is exactly what was
  reviewed. Requires `TF_MCP_ALLOW_APPLY=true` and a matching confirmation token.

---

## Use Case

A platform team manages Secure Firewall objects as code. Two problems recur:

1. **Console drift.** Somebody makes an "emergency" change in the FMC GUI. Nobody records
   it. Three weeks later the next `terraform apply` silently reverts it, or fails, and an
   outage investigation begins.
2. **Plan fatigue.** A plan touching 40 resources gets approved with a glance because
   reading `terraform plan` output carefully, every time, is genuinely hard.

**The solution.** `detect_drift` runs a refresh-only plan and reports exactly which
resources changed outside Terraform, with an interpretation the agent can relay in plain
language. `plan_workspace` plus `explain_plan` turn a 40-resource plan into a
resource-by-resource narrative that leads with `is_destructive`.

Because both are read-only, this is the lowest-risk way to introduce an AI agent to your
firewall estate — there is no code path from "agent read a plan" to "infrastructure
changed" unless an operator explicitly turns applies on.

**Outcomes and benefits**

| Before | After |
| --- | --- |
| Console drift discovered by the next failed apply | `detect_drift` on a schedule, reported in plain language |
| 40-resource plans approved with a glance | `explain_plan` narrates every add, change, and destroy |
| Destructive plans look like any other plan | `is_destructive: true` plus an explicit warning field |
| Secrets visible in plan and state output | Values Terraform marks sensitive are replaced before they leave the server |

**The challenge overcome.** Terraform's JSON output embeds real attribute values,
including credentials. Sending that to a hosted model would be a data-leak incident. The
server walks Terraform's own `before_sensitive` / `after_sensitive` / `sensitive_values`
markers and redacts every marked value **before the data leaves the process**.

**Where it could go next.** Scheduled drift reporting into chat, policy-as-code checks
(OPA/Sentinel) surfaced as tool output, and multi-workspace estate summaries. See
[../IDEAS.md](../IDEAS.md).

### Why an LLM belongs here

Plan explanation and drift detection give you most of the value of an AI agent with
almost none of the risk: dense JSON in, plain-English risk summary out, nothing changed.

---

## Sensitive value handling

Terraform marks sensitive attributes in its JSON output. This server walks
`before_sensitive` / `after_sensitive` / `sensitive_values` and replaces every marked
value with `<sensitive>` **before the data leaves the server**. Passwords and tokens
never reach the model context.

```json
{
  "address": "fmc_network_objects.app1",
  "action": "create",
  "changed_attributes": ["name", "value"],
  "after": { "name": "APP1_NET", "value": "10.10.20.0/24", "password": "<sensitive>" }
}
```

## Security model

- **Workspace allowlist.** `TF_MCP_WORKSPACES` is a list of `name=path` pairs. A caller
  names a workspace; it can never supply a path. Names not on the list are rejected, and
  the resolved directory is re-verified before every command.
- **Fixed argv, `shell=False`.** Subcommands and flags come from the server's own code.
  Nothing from the model reaches the command line.
- **Subcommand allowlist.** Only `version`, `init`, `validate`, `plan`, `show`, and
  `apply` can be executed at all.
- **Filtered child environment.** Only an explicit passthrough list (including the
  `TF_VAR_*` credentials) reaches the subprocess.
- **`init` uses `-backend=false`**, so inspection never touches remote state.
- **Apply uses the saved plan file**, which closes the classic
  plan-then-apply-something-else gap.
- **Hard timeout** (`TF_MCP_TIMEOUT`, default 900s) with process kill.
- **Destructive plans are flagged.** `is_destructive: true` plus an explicit `warning`
  field when any resource is deleted or replaced.

---

## Installation

### Prerequisites

| Requirement | Version | Where to get it |
| --- | --- | --- |
| Python | 3.11 or later | <https://www.python.org/downloads/> |
| Terraform CLI | 1.6 or later, on `PATH` | <https://developer.hashicorp.com/terraform/install> |
| Docker (optional) | any recent | <https://docs.docker.com/get-docker/> |
| An FMC | 7.0+ with REST API enabled | Your lab, or a [DevNet Sandbox](#related-sandbox) |
| An MCP-aware client | — | Claude Desktop, VS Code, Cursor, or any MCP agent |

Confirm Terraform is reachable before going further:

```bash
terraform version
```

If it is installed somewhere unusual, set `TERRAFORM_BINARY` to its absolute path.

### Clone and install

```bash
git clone https://github.com/ranilf2005/fw-automation.git
cd fw-automation/mcp_servers/terraform-mcp
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Verify the install

The unit tests run against fixture JSON — no Terraform binary, no FMC, no credentials:

```bash
pip install -r ../../requirements-dev.txt
pytest tests
```

## Configuration

Copy `.env.example` to `.env`:

```bash
TF_MCP_WORKSPACES=starter=/absolute/path/to/fw-automation/terraform

TF_VAR_fmc_url=https://fmc.example.local
TF_VAR_fmc_username=apiuser
TF_VAR_fmc_password=<export in your shell, not in the file>
TF_VAR_fmc_insecure_skip_verify=false

TF_MCP_ALLOW_APPLY=false
TF_MCP_TIMEOUT=900
```

> **State is sensitive.** `terraform.tfstate` records object values in cleartext and is
> gitignored. Use an encrypted remote backend for anything beyond a local lab.

---

## Usage

| `MCP_TRANSPORT` | Behaviour | Use for |
| --- | --- | --- |
| `stdio` (default) | MCP over stdin/stdout, no port | Desktop MCP clients |
| `http` | Serves `/mcp` on `MCP_HOST:MCP_PORT` | Shared deployments, Docker |

### Local Python (stdio)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
MCP_TRANSPORT=stdio python -m sfw_mcp_terraform
```

```json
{
  "mcpServers": {
    "cisco-fmc-terraform": {
      "command": ".venv/bin/python",
      "args": ["-m", "sfw_mcp_terraform"],
      "cwd": "/absolute/path/to/mcp_servers/terraform-mcp",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "TF_MCP_ALLOW_APPLY": "false"
      }
    }
  }
}
```

### Local Python (HTTP)

```bash
MCP_TRANSPORT=http MCP_HOST=127.0.0.1 MCP_PORT=8002 python -m sfw_mcp_terraform
```

No built-in authentication — front it with a TLS-terminating authenticating proxy before
exposing it beyond localhost.

### Docker

```bash
docker compose up -d --build
```

The image copies the Terraform binary from the official `hashicorp/terraform` image.
Unlike the other two servers, the workspace mount is **read-write** — Terraform must
write `.terraform/` and state. Point it at a dedicated IaC checkout, not a shared working
directory.

> Terraform is licensed **BUSL-1.1** by HashiCorp. The binary is used, not redistributed
> by this project. See [../../NOTICE](../../NOTICE).

---

### Manual testing

```bash
python client/test_client.py
```

Menu-driven access to versions, init, validate, plan, explain, drift, and state. It
prints a prominent warning when a plan is destructive.

---

### Automated tests

Unit tests cover the workspace allowlist (including traversal rejection), action
classification, plan summarisation, changed-attribute detection, sensitive-value
redaction in both plan and state, the apply gate, and confirmation-token binding. They
run against fixture JSON — no Terraform binary, no FMC.

```bash
pip install -r ../../requirements-dev.txt
pytest tests
```

---

### Integrating with LLM agents

1. Register the endpoint (stdio or HTTP).
2. `list_workspaces` → pick a target.
3. `init_workspace` → `validate_workspace` → `plan_workspace`.
4. `explain_plan` → talk the user through it. **Call out `is_destructive` explicitly.**
5. `apply_plan` with the change summary and token unchanged.
6. `detect_drift` afterwards to confirm the declared state holds.

A useful agent instruction:

> Always run `plan_workspace` and walk me through `explain_plan` before mentioning apply.
> If `is_destructive` is true, list every affected address and ask me to confirm each one.

### Worked example

> **User:** Did anyone change our firewall objects outside Terraform this week?

1. `detect_drift(workspace="starter")` → `drift_detected: true`, one resource.
2. `explain_plan` → `UPDATE fmc_network_objects.app1 (attributes: value)`.
3. Agent reports: *"APP1_NET was changed from 10.10.20.0/24 to 10.10.21.0/24 outside
   Terraform. Reconcile by updating the config, or apply to restore the declared state."*

All read-only. Nothing changed.

---

## Related Sandbox

You need an FMC for `plan`, `detect_drift`, and `show_state`. If you do not have a lab,
Cisco DevNet provides free sandboxes:

- [DevNet Sandbox catalogue](https://devnetsandbox.cisco.com/RM/Topology) — search for
  **Secure Firewall** or **Firepower**
- [Cisco Secure Firewall developer centre](https://developer.cisco.com/secure-firewall/)

Point `TF_VAR_fmc_url`, `TF_VAR_fmc_username`, and `TF_VAR_fmc_password` at the sandbox.
Sandbox FMCs present a self-signed certificate, so set
`TF_VAR_fmc_insecure_skip_verify=true` for a sandbox specifically.

`get_versions`, `init_workspace`, and `validate_workspace` need no FMC at all, so you can
validate your setup before you have one.

## Known issues

- **FMC provider resource names differ across major provider versions.** Run
  `terraform providers schema -json` and confirm against your own version. `main.tf`
  ships with the example resource commented out on purpose.
- **One plan file per workspace** (`mcp.tfplan`); a second `plan_workspace` overwrites it.
- **No remote-backend locking coordination.** Do not point several server instances at
  the same state.
- **`apply_plan` applies the saved plan only.** It cannot apply an ad-hoc change — that is
  the point, but it means you must re-plan after any edit.
- **`detect_drift` refreshes Terraform state.** It writes no firewall configuration, but
  it is not a completely side-effect-free read.
- **The Docker workspace mount is read-write**, unlike the other two servers in this
  collection, because Terraform must write `.terraform/` and state. Point it at a
  dedicated IaC checkout, not a shared working directory.
- **No built-in authentication on the HTTP transport.** Front it with a TLS-terminating
  authenticating reverse proxy.

Issues are tracked in
[GitHub Issues](https://github.com/ranilf2005/fw-automation/issues). Please use the
provided templates and include your Terraform and provider versions.

## Getting help

| I need... | Go to |
| --- | --- |
| Help with this server, a bug, or a feature idea | [GitHub Issues](https://github.com/ranilf2005/fw-automation/issues/new/choose) |
| To report a security vulnerability **in this repo** | [SECURITY.md](../../SECURITY.md) — do **not** open a public issue |
| Help with Cisco Secure Firewall itself | [Cisco TAC](https://www.cisco.com/c/en/us/support/index.html) |
| Terraform `fmc` provider issues | [CiscoDevNet/terraform-provider-fmc](https://github.com/CiscoDevNet/terraform-provider-fmc/issues) |
| Terraform CLI questions | [Terraform documentation](https://developer.hashicorp.com/terraform/docs) |
| MCP protocol questions | [modelcontextprotocol.io](https://modelcontextprotocol.io) |
| Community discussion | [Cisco Code Exchange Community](https://community.cisco.com/t5/code-exchange/bd-p/dev-code-exchange) |

Before opening an issue, run `get_versions` and `validate_workspace`, and re-run with
`LOG_LEVEL=DEBUG`. Full guidance is in [SUPPORT.md](../../SUPPORT.md).

## Getting involved

Contributions are welcome. Current focus areas:

- Scheduled drift reporting into chat or an ITSM record
- Policy-as-code (OPA / Sentinel) results surfaced as tool output
- Multi-workspace estate summaries
- Remote-backend locking coordination so multiple instances are safe

Development environment:

```bash
pip install -r requirements.txt
pip install -r ../../requirements-dev.txt
pre-commit install
pytest tests
```

Full instructions on *how* to contribute are in [CONTRIBUTING.md](../../CONTRIBUTING.md),
and all participation is governed by the [Code of Conduct](../../CODE_OF_CONDUCT.md).

## Credits and references

- [CiscoDevNet/terraform-provider-fmc](https://github.com/CiscoDevNet/terraform-provider-fmc) —
  the Terraform provider this server drives (MPL-2.0)
- [CiscoDevNet/CiscoFMC-MCP-server-community](https://github.com/CiscoDevNet/CiscoFMC-MCP-server-community) —
  the published FMC MCP server whose documentation structure this follows
- [FastMCP](https://github.com/jlowin/fastmcp) — the MCP server framework (Apache-2.0)
- [Model Context Protocol specification](https://modelcontextprotocol.io)
- [Terraform JSON output format](https://developer.hashicorp.com/terraform/internals/json-format) —
  the schema this server parses and sanitises

## Security

See [SECURITY.md](../../SECURITY.md), and the Generative AI disclosure in
[NOTICE](../../NOTICE).

## Licensing info

This code is licensed under the MIT License. See [LICENSE](../../LICENSE) for details.

The Terraform CLI is licensed **BUSL-1.1** by HashiCorp and the `CiscoDevNet/fmc`
provider is **MPL-2.0**. Both are invoked as external binaries, not vendored or
redistributed in source form by this project. Review the BUSL terms if you intend to
offer this as a competing hosted service. Full third-party attribution is in
[NOTICE](../../NOTICE).

**Not a Cisco product.** Not developed, endorsed, or supported by Cisco Systems, Inc.,
and not covered by a Cisco support contract or Cisco TAC.
