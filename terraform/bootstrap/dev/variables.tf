variable "location" {
  type    = string
  default = "southindia"
}

variable "storage_account_name" {
  description = "Globally unique lowercase state storage account name."
  type        = string
}

variable "allowed_public_ip_ranges" {
  type    = list(string)
  default = []
}

variable "github_repository" {
  type    = string
  default = "Elzabeth-L/Sentinel-Keyvault"
}
