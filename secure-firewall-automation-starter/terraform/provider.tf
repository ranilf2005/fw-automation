# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
#
# Do not hardcode credentials here. Supply them with environment variables:
#   export TF_VAR_fmc_url=https://fmc.example.local
#   export TF_VAR_fmc_username=apiuser
#   read -rs TF_VAR_fmc_password && export TF_VAR_fmc_password
provider "fmc" {
  fmc_username = var.fmc_username
  fmc_password = var.fmc_password
  fmc_host     = var.fmc_url

  # Certificate validation stays on unless you explicitly opt out for a lab FMC.
  fmc_insecure_skip_verify = var.fmc_insecure_skip_verify
}
