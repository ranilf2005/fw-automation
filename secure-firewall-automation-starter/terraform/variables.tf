variable "fmc_url" {
  type = string
}

variable "fmc_username" {
  type = string
}

variable "fmc_password" {
  type      = string
  sensitive = true
}
