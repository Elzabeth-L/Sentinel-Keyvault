variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "vnet_address_space" {
  type = list(string)
}

variable "subnet_prefixes" {
  description = "CIDRs keyed by app_gateway, aks, private_endpoints, and postgresql."
  type        = map(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}
