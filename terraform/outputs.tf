# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando

output "next_step" {
  description = "Reminder that resource names are provider-version specific."
  value = join(" ", [
    "Confirm exact resource names with your provider version, then add one simple",
    "object resource and run terraform plan.",
  ])
}

output "fmc_endpoint" {
  description = "FMC endpoint this configuration targets."
  value       = var.fmc_url
}

output "tls_verification_enabled" {
  description = "False means certificate validation is disabled - lab use only."
  value       = !var.fmc_insecure_skip_verify
}
