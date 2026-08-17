# Submitting to Cisco DevNet Code Exchange

How to take each server in this folder from "works on my laptop" to a published Code
Exchange entry, modelled on the already-published
[CiscoFMC-MCP-server-community](https://developer.cisco.com/codeexchange/github/repo/CiscoDevNet/CiscoFMC-MCP-server-community/).

## 1. What Code Exchange indexes

Code Exchange reads a **public GitHub repository** and renders its `README.md` as the
article body. The sidebar metadata (categories, products, AI type, deploy type,
capabilities, licence) comes from the repository's topics, licence file, and the
submission form.

That means: **the README *is* the article.** Everything else supports it.

## 2. Required files in the repository

The reference repo ships all of these. Each server folder here has an equivalent.

| File | Why it matters |
| --- | --- |
| `README.md` | Becomes the published article. Must lead with what the server does and its tool list. |
| `LICENSE` | Must be an OSI-approved licence. This project uses MIT, same as the reference repo. |
| `NOTICE` | Trademark, third-party attribution, and the "not a Cisco product" statement. |
| `SECURITY.md` | Private vulnerability reporting path. Required for the GitHub security policy badge. |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1. |
| `CONTRIBUTING.md` | How to contribute and the DCO/licensing certification. |
| `.env.example` | So nobody has to guess the configuration surface. |
| `requirements.txt` | Pinned dependencies. |
| `Dockerfile` + `docker-compose.yml` | Needed to claim the HTTP/Stream deploy type. |
| `tests/` | Demonstrates the project is maintained, not a snippet dump. |

In this repository those governance files live at the project root
([../LICENSE](../LICENSE), [../SECURITY.md](../SECURITY.md), and so on) and cover every
server. **If you split a server into its own repository, copy them in** — Code Exchange
checks the repository root.

## 3. Submission metadata

Each server folder contains a `codeexchange.json` with the values to enter on the
submission form. They follow the reference repo's classification:

| Field | Value |
| --- | --- |
| Categories | Security, Tools |
| Products | Secure Firewall |
| AI | MCP Servers |
| Deploy Type | HTTP/Stream |
| Features / Capabilities | Tools |
| Licence | MIT License |

Add these **GitHub repository topics** so the crawler classifies it correctly:

```
mcp  mcp-server  model-context-protocol  cisco  secure-firewall  fmc
firepower  network-automation  security  ai-agents
```

## 4. Pre-submission checklist

Run through this before you submit. Most rejections are avoidable.

### Content

- [ ] README opens with a one-paragraph description and a **bulleted tool list** — this
      is what appears in the article preview
- [ ] Numbered sections mirroring the reference article: configure → run → manual test →
      automated test → integrate with LLM agents
- [ ] Both stdio and HTTP transports documented, with a copy-pasteable `mcpServers`
      client config block
- [ ] Screenshots or a short demo, if you have them
- [ ] No marketing language, no unverifiable performance claims

### Legal and compliance

- [ ] OSI-approved licence file present at the repository root
- [ ] "Not a Cisco product / not supported by Cisco TAC" stated explicitly
- [ ] Cisco trademarks acknowledged, used only nominatively, and **not** used in the
      package, module, or repository name in a way implying Cisco origin
- [ ] Third-party dependency licences recorded (see [../NOTICE](../NOTICE)); check for
      GPL contamination if you vendor anything
- [ ] Generative AI disclosure present — Code Exchange displays its own disclaimer about
      third-party AI platforms, and your repo should match it

### Security

- [ ] `git log -p | grep -iE 'password|token|secret'` returns nothing real
- [ ] No `.env`, `*.tfvars`, `*.pem`, or vault password files tracked
- [ ] All sample data uses RFC 1918 / RFC 5737 addressing and `.example` domains
- [ ] TLS verification on by default
- [ ] Secret scanning and dependency audit run in CI and pass
- [ ] Write operations gated and documented

### Quality

- [ ] `pytest` passes with no live FMC required
- [ ] `ruff check`, `ruff format --check`, `mypy`, and `bandit` pass
- [ ] `docker compose up -d --build` produces a server that answers on `/mcp`
- [ ] A tagged release exists (the reference repo tagged `1.1.0`)

## 5. Submit

1. Push the repository public on GitHub with the topics above.
2. Go to [Code Exchange](https://developer.cisco.com/codeexchange/) and sign in with
   your Cisco account.
3. Choose **Submit your code**, paste the repository URL, and complete the metadata from
   `codeexchange.json`.
4. Cisco reviews for licence validity, working code, and appropriate content. Expect
   follow-up questions about the safety model for anything that writes to a firewall —
   the preview/confirm/apply design in these servers exists partly to make that
   conversation short.

## 6. After publication

- Watch the [Code Exchange Community](https://community.cisco.com/t5/code-exchange/bd-p/dev-code-exchange)
  for questions.
- Keep Dependabot PRs merged; a stale dependency set is the most common reason a
  published entry starts looking abandoned.
- Update `CHANGELOG.md` and cut a release for anything user-visible.
