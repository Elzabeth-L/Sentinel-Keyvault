variable "resource_group_name" {
  type = string
}

variable "zone_name" {
  type    = string
  default = "sentinel.vaultrix.in"
}

variable "frontdoor_endpoint_id" {
  type = string
}

variable "frontdoor_validation_token" {
  type = string
}

variable "dev_application_gateway_ip" {
  description = "Development Application Gateway public IP. Leave null until dev is deployed."
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
