# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
#
# Important:
# Resource support depends on the provider version and your FMC release. Resource
# names changed between major versions of CiscoDevNet/fmc, so before adding anything
# here run:
#   terraform providers schema -json | jq '.provider_schemas[].resource_schemas | keys'
# and confirm the exact resource names your installed provider supports.
#
# Workflow for this starter:
#   terraform init
#   terraform validate
#   terraform plan     # review every change before applying
#   terraform apply    # only against a lab FMC
#
# State safety: `terraform.tfstate` records object values in cleartext and is
# gitignored. Use an encrypted remote backend for anything beyond a local lab.
#
# Example placeholder only. Replace with the exact object resource supported by your
# provider version. Addressing below is RFC 1918 documentation space.
#
# resource "fmc_network_objects" "app1_net" {
#   name        = "APP1_NET_TF"
#   value       = "10.99.20.0/24"
#   type        = "Network"
#   description = "Managed by Terraform"
# }
