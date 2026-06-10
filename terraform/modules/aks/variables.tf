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

variable "tenant_id" {
  type = string
}

variable "kubernetes_version" {
  type    = string
  default = null
}

variable "aks_subnet_id" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "container_registry_id" {
  type = string
}

variable "api_server_authorized_ip_ranges" {
  type = list(string)

  validation {
    condition     = length(var.api_server_authorized_ip_ranges) > 0
    error_message = "At least one stable operator or CI CIDR must be provided for the public AKS API endpoint."
  }
}

variable "system_pool_vm_size" {
  type = string
}

variable "system_pool_min_count" {
  type = number
}

variable "system_pool_max_count" {
  type = number
}

variable "user_pool_enabled" {
  type = bool
}

variable "user_pool_vm_size" {
  type = string
}

variable "user_pool_min_count" {
  type = number
}

variable "user_pool_max_count" {
  type = number
}

variable "availability_zones" {
  type    = list(string)
  default = []
}

variable "service_cidr" {
  type = string
}

variable "dns_service_ip" {
  type = string
}

variable "pod_cidr" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
