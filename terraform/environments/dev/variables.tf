variable "location" {
  type    = string
  default = "southindia"
}

variable "name_suffix" {
  description = "Globally unique lowercase alphanumeric suffix."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{4,8}$", var.name_suffix))
    error_message = "Use a 4-8 character lowercase alphanumeric suffix."
  }
}

variable "owner" {
  type = string
}

variable "cost_center" {
  type = string
}

variable "additional_tags" {
  type    = map(string)
  default = {}
}

variable "operator_and_ci_cidrs" {
  description = "Stable public CIDRs allowed to reach the AKS API."
  type        = list(string)
}

variable "postgres_admin_password" {
  type      = string
  sensitive = true
}

variable "postgres_entra_admin" {
  type = object({
    object_id      = string
    principal_name = string
    principal_type = string
  })
  default = null
}

variable "gateway_certificate_secret_id" {
  type    = string
  default = null
}

variable "alert_email" {
  type    = string
  default = null
}
