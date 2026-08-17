# Pull Request

## What does this change?

<!-- One or two sentences. Link the issue it closes: Closes #123 -->

## Why?

<!-- The operational problem this solves. -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change
- [ ] Documentation only
- [ ] CI / tooling / dependencies

## Blast radius

- [ ] Read-only — makes no configuration changes
- [ ] Writes configuration to FMC
- [ ] Deletes configuration from FMC

If this writes or deletes, describe the **validation** and **rollback** steps:

<!-- ... -->

## How was this tested?

- [ ] `pre-commit run --all-files` passes
- [ ] `pytest` passes
- [ ] Validated against a **lab** FMC (version: `______`)
- [ ] Not applicable (docs/tooling only)

<!-- Describe the manual test you performed. -->

## Security and compliance checklist

- [ ] No credentials, tokens, private keys, or `.env` files are included
- [ ] No real hostnames, FQDNs, serial numbers, or production IP addresses — sample
      data uses RFC 1918 / RFC 5737 addressing and `.example` domains
- [ ] TLS verification remains enabled by default; any opt-out is explicit and documented
- [ ] No credentials or `Authorization` headers are written to logs
- [ ] Specific exceptions are caught, not bare `except Exception`
- [ ] New source files carry the SPDX header
- [ ] New dependencies are pinned and their licences are recorded in [NOTICE](../NOTICE)
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`

## Certification

- [ ] I wrote this code, or I have the right to submit it, and I license it under the
      repository's [MIT License](../LICENSE).
