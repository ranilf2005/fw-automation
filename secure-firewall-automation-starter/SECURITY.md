# Security Policy

## Scope

This repository is a **community learning and lab automation starter kit** for Cisco
Secure Firewall. It is not a Cisco product, it is not covered by a Cisco support
contract, and it carries no service-level agreement. See [SUPPORT.md](SUPPORT.md).

Vulnerabilities in Cisco Secure Firewall itself (FMC, FTD, FDM) are **out of scope**
for this repository. Report those directly to the
[Cisco Product Security Incident Response Team (PSIRT)](https://www.cisco.com/c/en/us/about/security-center/security-vulnerability-policy.html).

In scope for this repository:

- Code in `python/`, `mcp_servers/`, `ansible/`, and `terraform/`
- Credential handling, logging, and transport security defaults
- Dependency vulnerabilities that we can remediate by pinning or upgrading

## Reporting a Vulnerability

**Do not open a public GitHub issue for a security problem.**

Report privately using GitHub's
[Report a vulnerability](https://github.com/ranilf2005/fw-automation/security/advisories/new)
form. Please include:

1. Affected file(s) and version/commit
2. A description of the issue and its impact
3. Reproduction steps or a proof of concept
4. Any suggested remediation

We aim to acknowledge reports within 5 business days and to provide a remediation
plan or an explanation within 30 days.

Please practice coordinated disclosure: give us a reasonable window to publish a
fix before disclosing publicly.

## Supported Versions

Only the `main` branch receives security fixes. There are no long-term support
branches.

| Version | Supported |
| ------- | --------- |
| `main`  | Yes       |
| tagged releases | Best effort |

## Security Expectations for Users of This Repository

This code talks to a firewall management plane. Treat it accordingly.

### Credentials

- **Never commit `.env`, `*.tfvars`, `vault_pass.txt`, or populated `group_vars`.**
  These are excluded by [.gitignore](.gitignore), but verify before every push.
- Use a **dedicated FMC API user with least privilege**, not a full administrator
  account, and not a shared human account.
- Rotate the API user's password on a regular schedule.
- Prefer a secrets manager or `ansible-vault` over plaintext files.
- Terraform state can contain sensitive values. Use an encrypted remote backend for
  anything beyond a local lab.

### Transport security

- TLS certificate verification is **enabled by default** in this repository.
- `VERIFY_SSL=false` / `fmc_verify_ssl: false` disables certificate validation and
  exposes you to machine-in-the-middle attacks. Use it **only** against a lab FMC
  with a self-signed certificate, never against production.
- The preferred alternative to disabling verification is to trust the FMC CA
  explicitly with `FMC_CA_BUNDLE=/path/to/ca.pem`.

### Blast radius

- Run every workflow against a **lab FMC or a non-production access policy** first.
- The MCP servers in `mcp_servers/` default to **read-only**. Write and destructive
  operations are opt-in via explicit environment flags and are logged.
- Review `outputs/logs/` and `outputs/reports/` before sharing them; they can contain
  object names, IP addressing, and policy structure from your environment.

### Automated checks

Every pull request runs dependency auditing (`pip-audit`), static analysis
(`bandit`, `ruff`), secret scanning (`gitleaks`), and CodeQL. See
[.github/workflows/ci.yml](.github/workflows/ci.yml).
