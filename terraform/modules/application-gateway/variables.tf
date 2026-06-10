variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "backend_ip_address" {
  type = string
}

variable "backend_port" {
  type    = number
  default = 80
}

variable "backend_protocol" {
  type    = string
  default = "Http"
}

variable "custom_domain" {
  type = string
}

variable "certificate_secret_id" {
  description = "Versionless Key Vault secret ID for the TLS certificate. Null creates an HTTP listener for initial bootstrap."
  type        = string
  default     = null
}

variable "key_vault_id" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "zones" {
  type    = list(string)
  default = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
