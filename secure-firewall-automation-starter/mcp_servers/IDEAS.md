# MCP Server Ideas for Cisco Secure Firewall

Working notes on why these three servers were built, and a backlog of further concepts.
Use this when pitching or scoping additional Code Exchange submissions.

## The gap being filled

The published
[CiscoFMC-MCP-server-community](https://developer.cisco.com/codeexchange/github/repo/CiscoDevNet/CiscoFMC-MCP-server-community/)
server is excellent at one job: **finding which access rules match an indicator**
(`find_rules_by_ip_or_fqdn`, `find_rules_for_target`, `search_access_rules`). It is a
read-and-search tool for incident response and audit.

What it deliberately does not do is *change* anything, and it only speaks one
automation dialect. Real firewall teams run three:

| Dialect | Question it answers | Typical user |
| --- | --- | --- |
| REST API | "Make this one change now" | Ops engineer working a ticket |
| Ansible | "Run the approved procedure" | Change-window operator |
| Terraform | "Does reality still match what we declared?" | Platform / IaC team |

Three servers, one per dialect, each shipped separately so a team can adopt only the
one that matches how they already work.

---

## Server 1 — Secure Firewall REST API MCP Server

**Pitch:** give an agent the FMC REST API with a safety harness, so it can investigate
*and* propose changes without ever being one hallucination away from a policy edit.

**Differentiator:** the **preview → confirm → apply** pipeline. `preview_object_changes`
returns a plan plus a token derived from a hash of that plan.
`apply_object_changes` refuses any token that does not match the plan it was given.
The model physically cannot mutate FMC in one call, and cannot apply a plan a human
did not see.

**Tools**

| Tool | Read/Write | Purpose |
| --- | --- | --- |
| `list_fmc_profiles` | R | Discover configured FMC instances |
| `get_inventory` | R | Domains, devices, policies, counts |
| `search_objects` | R | Find hosts/networks/services by name, value, or CIDR containment |
| `find_object_usage` | R | Which access rules reference this object — the "can I safely delete it?" question |
| `list_access_rules` | R | Paginated rule listing with filters |
| `get_deployment_status` | R | Pending changes and deployment state |
| `preview_object_changes` | R | Diff proposed objects against FMC, return plan + token |
| `apply_object_changes` | **W** | Execute a previously previewed plan |

**Who wants it:** SOC and NOC engineers, anyone doing object hygiene, teams answering
"is this IP allowed anywhere?" and then acting on the answer.

---

## Server 2 — Ansible MCP Server for Secure Firewall

**Pitch:** teams already have approved playbooks. Let the agent *run the runbook*
instead of inventing API calls.

**Differentiator:** the agent never writes automation — it selects from an **allowlist**
of reviewed playbooks and supplies validated variables. Everything a compliance auditor
cares about (what ran, with what inputs, what changed) is preserved, because the unit of
execution is still the playbook a human approved.

**Tools**

| Tool | Read/Write | Purpose |
| --- | --- | --- |
| `list_playbooks` | R | Allowlisted playbooks with descriptions and required variables |
| `describe_playbook` | R | Tasks, variables, and whether the playbook mutates state |
| `check_syntax` | R | `ansible-playbook --syntax-check` |
| `dry_run_playbook` | R | `--check --diff`, returns the would-change set |
| `run_playbook` | **W** | Real execution, requires a token from `dry_run_playbook` |
| `get_last_run` | R | Redacted log of the most recent execution |

**Security notes:** fixed argv, `shell=False`, playbook path resolved and confined to
the repo's `ansible/` directory, extra vars passed as a temp JSON file rather than
interpolated into a command line, hard timeout, output cap, secrets redacted.

**Who wants it:** change-window operators, MSPs running the same procedure across many
customers, anyone who needs an audit trail more than they need flexibility.

---

## Server 3 — Terraform MCP Server for Secure Firewall

**Pitch:** drift detection and plan explanation in natural language. `terraform plan`
output is dense; an LLM is genuinely good at summarising it — and summarising is a
read-only operation, so the risk profile is excellent.

**Differentiator:** parses `terraform show -json` into structured, **sanitised** change
sets. Sensitive attribute values are redacted before they enter the model context.
`apply` is disabled by default and gated behind both an env flag and a plan-bound token.

**Tools**

| Tool | Read/Write | Purpose |
| --- | --- | --- |
| `list_workspaces` | R | Allowlisted Terraform directories |
| `get_versions` | R | Terraform and provider versions |
| `init_workspace` | R | `terraform init -backend=false` |
| `validate_workspace` | R | `terraform validate -json` |
| `plan_workspace` | R | Plan to a file, return a structured summary + token |
| `explain_plan` | R | Resource-by-resource breakdown of adds/changes/destroys |
| `detect_drift` | R | Refresh-only plan — what changed outside Terraform |
| `show_state` | R | Sanitised state summary |
| `apply_plan` | **W** | Apply a saved plan, requires token *and* `TF_MCP_ALLOW_APPLY=true` |

**Who wants it:** platform teams running Secure Firewall as code, anyone who has ever
been surprised by a console change that broke the next `apply`.

---

## Backlog — further server concepts

Ranked by value-to-effort. None of these are built yet.

1. **Change-request MCP server.** Bridge ITSM and firewall. Reads a change ticket,
   produces the object/rule plan, and writes the validation evidence back to the ticket.
   High value, needs an ITSM integration.
2. **Policy-hygiene MCP server.** Shadowed rules, duplicate objects, unused objects,
   overly permissive `any-any`, rules with no hit count. Read-only, so very low risk and
   an easy first adoption. Extends `python/reports/compliance_report.py`.
3. **Event and log MCP server.** Query connection and intrusion events to answer
   "did that rule change break anything?" Pairs naturally with the REST server.
4. **Multi-FMC estate MCP server.** Config comparison across FMCs — object naming
   consistency, policy divergence between sites. Relevant to MSPs.
5. **Migration assistant MCP server.** Parse ASA configuration and propose the FTD
   equivalent, with an explicit unsupported-construct report.
6. **Backup and restore MCP server.** Scheduled config backup, retention, and
   point-in-time diff. Mostly read; restore would need the strictest gating of all.

## Design principles worth reusing

- **Split every mutation into preview and apply.** One tool call must never be able to
  change production. This is the single most important pattern in this repo.
- **Bind the confirmation token to the plan content**, not to a session. A stale or
  substituted plan then fails closed.
- **Return structured JSON, not prose.** The model is better at reasoning over
  `{"action": "create", "name": "..."}` than over a rendered table, and structured output
  is far cheaper in context.
- **Cap everything.** Timeouts on subprocesses, size caps on responses, page caps on
  API listings. An agent will find the pathological case.
- **Make the read-only path genuinely useful on its own.** Most teams will never enable
  writes, and the server still has to earn its place.
