variable "environment" {
  description = "Environment name."
  type        = string
}

variable "location" {
  description = "Azure region for the state resource group."
  type        = string
}

variable "resource_group_name" {
  description = "State resource group name."
  type        = string
}

variable "storage_account_name" {
  description = "Globally unique state storage account name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "Storage account names must be 3-24 lowercase alphanumeric characters."
  }
}

variable "container_name" {
  description = "Blob container used for Terraform state."
  type        = string
  default     = "tfstate"
}

variable "allowed_public_ip_ranges" {
  description = "Stable operator and CI public IPv4 addresses or supported CIDRs allowed to reach the state endpoint. Use a plain address for a single IP."
  type        = list(string)
  default     = []
}

variable "github_identity_name" {
  description = "User-assigned identity used by GitHub Actions."
  type        = string
}

variable "github_repository" {
  description = "GitHub repository in owner/name form."
  type        = string
  default     = "Elzabeth-L/Sentinel-Keyvault"
}

variable "github_environment" {
  description = "GitHub environment trusted by the federated credential."
  type        = string
}

variable "assign_subscription_deployment_roles" {
  description = "Assign Contributor and RBAC Administrator to the GitHub identity at subscription scope."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to state resources."
  type        = map(string)
  default     = {}
}
