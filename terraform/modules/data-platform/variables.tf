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

variable "key_vault_name" {
  type = string
}

variable "storage_account_name" {
  type = string
}

variable "container_registry_name" {
  type = string
}

variable "postgres_server_name" {
  type = string
}

variable "postgres_database_name" {
  type    = string
  default = "sentinel"
}

variable "postgres_admin_login" {
  type    = string
  default = "sentineladmin"
}

variable "postgres_admin_password" {
  description = "Bootstrap password supplied at runtime. It is sensitive and must never be committed."
  type        = string
  sensitive   = true
}

variable "postgres_sku_name" {
  type = string
}

variable "postgres_storage_mb" {
  type = number
}

variable "postgres_backup_retention_days" {
  type = number
}

variable "postgres_geo_redundant_backup_enabled" {
  type    = bool
  default = false
}

variable "postgres_zone" {
  type    = string
  default = null
}

variable "postgres_ha_enabled" {
  type    = bool
  default = false
}

variable "postgres_ha_standby_zone" {
  type    = string
  default = null
}

variable "postgres_entra_admin" {
  description = "Optional Entra administrator."
  type = object({
    object_id      = string
    principal_name = string
    principal_type = string
  })
  default = null
}

variable "private_endpoint_subnet_id" {
  type = string
}

variable "postgres_subnet_id" {
  type = string
}

variable "private_dns_zone_ids" {
  type = map(string)
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "workload_identities" {
  type = map(object({
    id              = string
    client_id       = string
    principal_id    = string
    namespace       = string
    service_account = string
  }))
}

variable "workload_identity_keys" {
  type = set(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}
