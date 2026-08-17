# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
#
# The CiscoDevNet/fmc provider is licensed MPL-2.0 and is downloaded from the public
# Terraform Registry by `terraform init`. See the NOTICE file.
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    fmc = {
      source = "CiscoDevNet/fmc"
      # Pinned to a major version so `terraform init` cannot silently pull a
      # breaking release. Bump deliberately after reading the provider changelog.
      version = "~> 1.4"
    }
  }
}
