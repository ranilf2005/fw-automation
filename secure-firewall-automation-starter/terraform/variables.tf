# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors

variable "fmc_url" {
  description = "Base URL of the FMC, including scheme. Must be https."
  type        = string

  validation {
    condition     = can(regex("^https://", var.fmc_url))
    error_message = "fmc_url must start with https:// - do not send API credentials over plaintext HTTP."
  }
}

variable "fmc_username" {
  description = "FMC API user. Use a dedicated least-privilege account, not a shared admin."
  type        = string

  validation {
    condition     = length(var.fmc_username) > 0
    error_message = "fmc_username must not be empty."
  }
}

variable "fmc_password" {
  description = "FMC API password. Supply via TF_VAR_fmc_password, never in a committed file."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.fmc_password) > 0
    error_message = "fmc_password must not be empty."
  }
}

variable "fmc_insecure_skip_verify" {
  description = <<-EOT
    Disable TLS certificate validation. LAB ONLY - this removes protection against
    machine-in-the-middle attacks on your FMC API credentials. Leave false in any
    environment you care about.
  EOT
  type        = bool
  default     = false
}
