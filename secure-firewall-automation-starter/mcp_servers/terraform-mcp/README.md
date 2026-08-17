# Terraform MCP Server for Cisco Secure Firewall

MCP server that gives an AI agent the Terraform workflow for Cisco Secure Firewall:
validate, plan, **explain**, and detect drift — all read-only — with `apply` disabled by
default and gated behind a plan-bound confirmation token.

Plan explanation is where a language model genuinely earns its place. `terraform plan`
output is dense and easy to skim past; turning it into *"this deletes two rules and
replaces the object three rules depend on"* is exactly what an LLM is good at, and it is
a **read-only** operation.

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

## 1. Configure

Terraform >= 1.6 must be installed and on `PATH` (or set `TERRAFORM_BINARY`).

Copy `.env.example` to `.env`:

```bash
TF_MCP_WORKSPACES=starter=/absolute/path/to/secure-firewall-automation-starter/terraform

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

## 2. Run the MCP server

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

## 3. Manual testing

```bash
python client/test_client.py
```

Menu-driven access to versions, init, validate, plan, explain, drift, and state. It
prints a prominent warning when a plan is destructive.

---

## 4. Automated tests

Unit tests cover the workspace allowlist (including traversal rejection), action
classification, plan summarisation, changed-attribute detection, sensitive-value
redaction in both plan and state, the apply gate, and confirmation-token binding. They
run against fixture JSON — no Terraform binary, no FMC.

```bash
pip install -r ../../requirements-dev.txt
pytest tests
```

---

## 5. Integrating with LLM agents

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

## Limits

- FMC provider resource names differ across major provider versions. Run
  `terraform providers schema -json` and confirm against your own version.
- One plan file per workspace (`mcp.tfplan`); a second `plan_workspace` overwrites it.
- No remote-backend locking coordination. Do not point several server instances at the
  same state.
- `apply_plan` applies the saved plan only. It cannot apply an ad-hoc change.

## Security

See [../../SECURITY.md](../../SECURITY.md), and the Generative AI disclosure in
[../../NOTICE](../../NOTICE).

## Licence

MIT — see [../../LICENSE](../../LICENSE). Not a Cisco product; not supported by Cisco TAC.
