# Submitting to Cisco DevNet Code Exchange

How to take each server in this folder from "works on my laptop" to a published Code
Exchange entry. Verified against the live
[submission page](https://developer.cisco.com/codeexchange/submit/) and the official
[CiscoDevNet/code-exchange-repo-template](https://github.com/CiscoDevNet/code-exchange-repo-template/blob/main/manual-sample-repo/README.md).

## 1. The four acceptance conditions

Cisco states these on the submission form. A project must be:

| # | Condition | Status here |
| --- | --- | --- |
| 1 | **Relevant to Cisco technologies** (e.g. AI, Sustainability, Observability) | Yes — Cisco Secure Firewall + MCP servers for AI agents |
| 2 | **Publicly available on GitHub** | Yes — <https://github.com/ranilf2005/fw-automation> |
| 3 | Licensed under an [OSI-approved open source licence](https://opensource.org/licenses/alphabetical/) **or** the [Cisco Sample Code License](https://developer.cisco.com/site/license/cisco-sample-code-license/) | Yes — MIT, which is OSI-approved. See [LICENSE](../LICENSE) |
| 4 | **Clear technical documentation** (README) on how to use the code, applied use cases, and linked resources | Yes — every README follows the official template |

### A note on licence choice

The two options are not equivalent:

- **MIT (what this project uses)** — OSI-approved, permissive, no field-of-use
  restriction. Appropriate for a community project not owned by Cisco.
- **Cisco Sample Code License v1.1** — *not* OSI-approved. Clause 1 licenses the code
  "solely for use with Cisco products and services", and clause 2 forbids using it
  independent of, or to replicate or compete with, a Cisco product. It also asserts Cisco
  ownership of the sample code. It is intended for code Cisco itself publishes, and is
  the wrong choice for a third-party repository.

**If you are a Cisco employee publishing under a personal account**, check your
employer's open-source policy before publishing, and confirm the copyright holder in
[LICENSE](../LICENSE) is what that policy requires. It currently reads
`Copyright (c) 2026 Ranil Fernando`.

## 2. The README *is* the article

Code Exchange reads a **public GitHub repository**, renders its root `README.md` as the
published page, and uses the first few content lines for the tile — or the GitHub repo
Description, if you set one. The sidebar metadata (categories, products, AI type, deploy
type, capabilities, licence) comes from the repository's topics, licence file, and the
submission form.

Two consequences:

- **Lead with substance.** The first paragraph must say what the code does and why it
  matters — not "this repo contains...".
- **Set a GitHub Description** on the repo so the tile text is deliberate.

Use [GitHub Flavored Markdown](https://github.github.com/gfm/). reStructuredText support
is incomplete.

## 3. Required README structure

From the official template. Sections marked **required** must be present.

| Section | Status | Notes |
| --- | --- | --- |
| `# Project Title` | **required** | Best practice #10: use the *full use case name*, not a bare project name. E.g. `# Devicebanner, updates the banner motd on a network device` |
| Description | **required** | Problem, how the code solves it, challenges overcome, ideas for extension |
| Technology stack | recommended | Languages, and whether standalone or a module |
| Status | recommended | Alpha / Beta / 1.1 — set expectations |
| Screenshot | recommended | If the code has visual output |
| `## Use Case` | optional | Problem statement, solution, outcomes, benefits, metrics |
| `## Installation` | **required** | Must call out every dependency, and be kept working |
| `## Configuration` | optional | Every configurable value |
| `## Usage` | **required** | Be specific; format code and command output properly |
| `## White Paper` | optional | Only if one exists |
| `## Related Sandbox` | optional | Link a [DevNet Sandbox](https://devnetsandbox.cisco.com/RM/Topology) plus instructions to run against it |
| `## Links to DevNet Learning Labs` | optional | Only if relevant |
| `## Solutions on Ecosystem Exchange` | optional | Only if relevant |
| `## Known issues` | optional | Real shortcomings, plus how to file issues |
| `## Getting help` | optional | Issues list, community links |
| `## Getting involved` | optional | Focus areas + link to `CONTRIBUTING.md` |
| `## Credits and references` | optional | Inspiring projects, related projects, sources |
| Licensing statement | **required in practice** | "This code is licensed under the *X* License. See [LICENSE](../LICENSE) for details." |

Every README in this folder — and the [repository root README](../README.md) — follows
this structure.

> Delete the template's own "Additional information", "Licensing info" instructions, and
> "Best practices" sections from your README. They are guidance *for you*, not content
> for readers.

## 4. Required files in the repository

| File | Why it matters |
| --- | --- |
| `README.md` | Becomes the published article. Must lead with what the server does and its tool list. |
| `LICENSE` | Must be OSI-approved or the Cisco Sample Code License. This project uses MIT. |
| `NOTICE` | Trademark, third-party attribution, and the "not a Cisco product" statement. Required by good practice #8 when GPLv3 or Apache 2.0 dependencies are involved. |
| `SECURITY.md` | Private vulnerability reporting path. Required for the GitHub security policy badge. |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1. |
| `CONTRIBUTING.md` | How to contribute and the licensing certification. |
| `.env.example` | So nobody has to guess the configuration surface. |
| `requirements.txt` | Pinned dependencies. |
| `Dockerfile` + `docker-compose.yml` | Needed to claim the HTTP/Stream deploy type (good practice #9). |
| `tests/` | Demonstrates the project is maintained, not a snippet dump. |

In this repository the governance files live at the **repository root**
([../LICENSE](../LICENSE), [../SECURITY.md](../SECURITY.md), and so on), which is exactly
where Code Exchange looks. **If you split a server into its own repository, copy them
in.**

## 5. Cisco's good and bad practices

Cisco publishes these in the template. Checked against this project:

### Good practices

| # | Practice | Status |
| --- | --- | --- |
| 1 | Keep passwords/API keys out of source; parse from env or arguments | **Done** — all credentials come from `.env` / environment / `ansible-vault`; nothing is committed |
| 2 | Document how to run on Windows, macOS, and Linux | **Done** — every Installation section has all three |
| 3 | Print usage when run without input; support `-h` / `--help` | **Done** — every `python/` script uses a shared `argparse` helper; `--help` documents the arguments and required environment, and a missing input file errors clearly with exit code 2 |
| 4 | Catch errors and print useful information | **Done** — specific exception types, per-row CREATED/SKIP/FAILED reporting with reasons |
| 5 | Handle missing or misformatted parameters | **Done** — `validate_*.py` scripts; MCP servers validate every tool argument |
| 6 | Link resources where users can test the code (DevNet sandboxes) | **Done** — `## Related Sandbox` in every README |
| 7 | Link where to download prerequisites | **Done** — Prerequisites tables link every dependency |
| 8 | Add a NOTICE file if using GPLv3 or Apache 2.0 | **Done** — [NOTICE](../NOTICE) records all third-party licences |
| 9 | Dockerise the app or part of it | **Done** — all three MCP servers ship a Dockerfile and compose file |
| 10 | Title = full use case name | **Done** |
| 11 | SecureX workflow analyser | N/A |
| 12 | Use [OSSF Scorecard](https://github.com/ossf/scorecard) to judge dependency safety | **Done** — [scorecard.yml](../.github/workflows/scorecard.yml) runs weekly and on push, alongside `pip-audit`, Dependabot, and CodeQL |

### Bad practices to avoid

| # | Anti-pattern | Status |
| --- | --- | --- |
| 1 | Low-quality screenshots | N/A — no screenshots yet |
| 2 | Users must rename files like `variables_template.py` | **Avoided** — `.env.example` → `.env` is a documented copy, not a rename of source |
| 3 | Users must put credentials in source files | **Avoided** |
| 4 | Ambiguous endpoint/IP format | **Avoided** — the root README states `FMC_HOST` must include the scheme and have no trailing slash |

## 6. Submission metadata

Each server folder contains a `codeexchange.json` with the values to enter on the
submission form:

| Field | Value |
| --- | --- |
| Categories | Security, Tools |
| Products | Secure Firewall |
| AI | MCP Servers |
| Deploy Type | HTTP/Stream |
| Features / Capabilities | Tools |
| Licence | MIT License |

### GitHub repository Description

Set this in **GitHub → your repo → About → ⚙ → Description**. Code Exchange uses it for
the tile text in preference to the README, so it is worth getting right. Keep it under
GitHub's 350-character limit:

```text
Automate Cisco Secure Firewall (FMC-managed FTD) with Python, Ansible, and Terraform, plus three MCP servers that let an AI agent search policy, trace object usage, and propose changes behind a preview-and-confirm gate. Read-only by default, TLS on by default, CSV-driven, lab-tested.
```

### GitHub repository topics

Same **About** panel, Topics field. These drive how the Code Exchange crawler classifies
the entry:

```text
mcp
mcp-server
model-context-protocol
cisco
secure-firewall
fmc
firepower
network-automation
security
ai-agents
ansible
terraform
python
```

With the [GitHub CLI](https://cli.github.com/) installed and authenticated, both can be
set in two commands:

```bash
gh repo edit ranilf2005/fw-automation \
  --description "Automate Cisco Secure Firewall (FMC-managed FTD) with Python, Ansible, and Terraform, plus three MCP servers that let an AI agent search policy, trace object usage, and propose changes behind a preview-and-confirm gate. Read-only by default, TLS on by default, CSV-driven, lab-tested."

gh repo edit ranilf2005/fw-automation \
  --add-topic mcp,mcp-server,model-context-protocol,cisco,secure-firewall,fmc,firepower,network-automation,security,ai-agents,ansible,terraform,python
```

## 7. Open gaps

One item remains, and it is deliberate:

1. **Scorecard publishing.** `publish_results` is `false` in
   [scorecard.yml](../.github/workflows/scorecard.yml) because publishing requires opting
   the repo in to the OpenSSF REST API first. The workflow runs and uploads its SARIF to
   code scanning either way; only the public badge needs the opt-in.

## 8. Splitting a server into its own repository

Each server folder is self-contained and can be submitted independently. If you do split
one out, **copy these into the new repository root**, because Code Exchange checks the
root:

```
LICENSE  NOTICE  README.md  SECURITY.md  SUPPORT.md
CONTRIBUTING.md  CODE_OF_CONDUCT.md  CHANGELOG.md
```

Then fix the relative links in the copied README (`../../LICENSE` → `LICENSE`, and so on)
and add the `requirements-dev.txt` and `pyproject.toml` the tests depend on.

## 9. Pre-submission checklist

Run through this before you submit. Most rejections are avoidable. Ticked items were
verified against this repository on 2026-08-17.

### Content

- [x] README opens with a substantive description, not "this repo contains"
- [x] Title is the full use case name (good practice #10)
- [x] `## Installation` and `## Usage` are present, specific, and tested
- [x] Windows, macOS, and Linux instructions are all present (good practice #2)
- [x] A `## Related Sandbox` link with instructions to run against it (good practice #6)
- [x] `## Known issues`, `## Getting help`, `## Getting involved`, and
      `## Credits and references` present
- [x] Both stdio and HTTP transports documented, with a copy-pasteable `mcpServers`
      client config block
- [x] GitHub repo Description and topics are set
- [x] Screenshots or a short demo, if you have them — diagrams in [../docs/images](../docs/images)
- [x] No marketing language, no unverifiable performance claims

### Legal and compliance

- [x] OSI-approved licence (or the Cisco Sample Code License) at the repository **root**
- [x] Copyright holder is a real name or entity, not a placeholder
- [x] A one-line licensing statement in the README pointing at the LICENSE file
- [x] "Not a Cisco product / not supported by Cisco TAC" stated explicitly
- [x] Cisco trademarks acknowledged, used only nominatively, and **not** used in the
      package, module, or repository name in a way implying Cisco origin
- [x] Third-party dependency licences recorded (see [../NOTICE](../NOTICE)); check for
      GPL contamination if you vendor anything
- [x] Generative AI disclosure present — Code Exchange displays its own disclaimer about
      third-party AI platforms, and your repo should match it

### Security

- [x] `git log -p | grep -iE 'password|token|secret'` returns nothing real
- [x] No `.env`, `*.tfvars`, `*.pem`, or vault password files tracked
- [x] All sample data uses RFC 1918 / RFC 5737 addressing and `.example` domains
- [x] TLS verification on by default
- [x] Secret scanning and dependency audit run in CI and pass
- [x] Write operations gated and documented

### Quality

- [x] `pytest` passes with no live FMC required
- [x] `ruff check`, `ruff format --check`, `mypy`, and `bandit` pass
- [x] All three container images build in CI
- [ ] `docker compose up -d --build` produces a server that answers on `/mcp` — CI builds
      the images but does not run them, so verify this by hand against your own lab
- [x] A tagged release exists

## 10. Submit

1. Push the repository public on GitHub with the Description and topics set.
2. Go to <https://developer.cisco.com/codeexchange/submit/> and sign in with your Cisco
   account.
3. Paste the GitHub project URL and choose **Share Project**. Complete the metadata from
   `codeexchange.json`.
4. Cisco reviews for licence validity, working code, and appropriate content. Expect
   follow-up questions about the safety model for anything that writes to a firewall —
   the preview/confirm/apply design in these servers exists partly to make that
   conversation short.

If your documentation is not ready, the submission page also offers the Markdown template
to start from, then re-submit.

## 11. After publication

- Watch the [Code Exchange Community](https://community.cisco.com/t5/code-exchange/bd-p/dev-code-exchange)
  for questions.
- Keep Dependabot PRs merged; a stale dependency set is the most common reason a
  published entry starts looking abandoned.
- Update [../CHANGELOG.md](../CHANGELOG.md) and cut a release for anything user-visible.
