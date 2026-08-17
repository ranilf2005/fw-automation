# Support

## This project is community-maintained

The Secure Firewall Automation Starter Pack (`ranilf2005/fw-automation`) is
**not a Cisco product**. Cisco TAC will not
take a case for anything in this repository, and there is no SLA. See
[NOTICE](NOTICE).

## Where to go

| I need... | Go to |
| --- | --- |
| Help using this repo, a bug, a feature idea | [GitHub Issues](https://github.com/ranilf2005/fw-automation/issues/new/choose) |
| To report a security vulnerability in this repo | [SECURITY.md](SECURITY.md) — do **not** open an issue |
| Help with Cisco Secure Firewall itself | [Cisco TAC](https://www.cisco.com/c/en/us/support/index.html) |
| A security vulnerability in a Cisco product | [Cisco PSIRT](https://www.cisco.com/c/en/us/about/security-center/security-vulnerability-policy.html) |
| FMC REST API questions | [Cisco DevNet Secure Firewall](https://developer.cisco.com/secure-firewall/) |
| Community discussion | [Cisco Code Exchange Community](https://community.cisco.com/t5/code-exchange/bd-p/dev-code-exchange) |
| `cisco.fmcansible` collection issues | [CiscoDevNet/FMCAnsible](https://github.com/CiscoDevNet/FMCAnsible/issues) |
| Terraform `fmc` provider issues | [CiscoDevNet/terraform-provider-fmc](https://github.com/CiscoDevNet/terraform-provider-fmc/issues) |

## Before you open an issue

Most problems in this space come from FMC version differences in API payload schemas.
Please check first:

1. Confirm the endpoint and payload in **FMC API Explorer** on your own FMC
   (`https://<fmc-host>/api/api-explorer`).
2. Re-run with debug logging: `LOG_LEVEL=DEBUG`.
3. Check [docs/TESTING.md](docs/TESTING.md) for the validation sequence.

Then include in your issue:

- FMC version and FTD version
- Python / Ansible / Terraform version
- The exact command you ran
- Full error output with **credentials and hostnames redacted**

## Response expectations

This is maintained on a best-effort, volunteer basis. Issues are triaged when time
allows. Pull requests are the fastest path to a fix — see [CONTRIBUTING.md](CONTRIBUTING.md).
