resource "azurerm_key_vault" "this" {
  name                          = var.key_vault_name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  tenant_id                     = var.tenant_id
  sku_name                      = "premium"
  rbac_authorization_enabled    = true
  public_network_access_enabled = false
  purge_protection_enabled      = true
  soft_delete_retention_days    = var.environment == "prod" ? 90 : 30

  network_acls {
    bypass         = "AzureServices"
    default_action = "Deny"
  }

  tags = var.tags
}

resource "azurerm_storage_account" "application" {
  name                              = var.storage_account_name
  resource_group_name               = var.resource_group_name
  location                          = var.location
  account_tier                      = "Standard"
  account_replication_type          = var.environment == "prod" ? "ZRS" : "LRS"
  account_kind                      = "StorageV2"
  min_tls_version                   = "TLS1_2"
  public_network_access_enabled     = false
  allow_nested_items_to_be_public   = false
  shared_access_key_enabled         = false
  default_to_oauth_authentication   = true
  cross_tenant_replication_enabled  = false
  infrastructure_encryption_enabled = var.environment == "prod"

  blob_properties {
    versioning_enabled  = true
    change_feed_enabled = true

    delete_retention_policy {
      days = var.environment == "prod" ? 30 : 14
    }

    container_delete_retention_policy {
      days = var.environment == "prod" ? 30 : 14
    }
  }

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }

  tags = var.tags
}

resource "azurerm_storage_container" "login_events" {
  name                  = "sentinel-login-events"
  storage_account_id    = azurerm_storage_account.application.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "audit_exports" {
  name                  = "sentinel-audit-exports"
  storage_account_id    = azurerm_storage_account.application.id
  container_access_type = "private"
}

resource "azurerm_container_registry" "this" {
  name                          = var.container_registry_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = "Premium"
  admin_enabled                 = false
  public_network_access_enabled = false
  anonymous_pull_enabled        = false
  data_endpoint_enabled         = false
  export_policy_enabled         = false
  network_rule_bypass_option    = "AzureServices"
  retention_policy_in_days      = var.environment == "prod" ? 30 : 14
  zone_redundancy_enabled       = var.environment == "prod"
  tags                          = var.tags
}

resource "azurerm_postgresql_flexible_server" "this" {
  name                          = var.postgres_server_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = "16"
  delegated_subnet_id           = var.postgres_subnet_id
  private_dns_zone_id           = var.private_dns_zone_ids["postgres"]
  public_network_access_enabled = false
  administrator_login           = var.postgres_admin_login
  administrator_password        = var.postgres_admin_password
  zone                          = var.postgres_zone
  storage_mb                    = var.postgres_storage_mb
  sku_name                      = var.postgres_sku_name
  backup_retention_days         = var.postgres_backup_retention_days
  geo_redundant_backup_enabled  = var.postgres_geo_redundant_backup_enabled

  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = true
    tenant_id                     = var.tenant_id
  }

  dynamic "high_availability" {
    for_each = var.postgres_ha_enabled ? [1] : []

    content {
      mode                      = "ZoneRedundant"
      standby_availability_zone = var.postgres_ha_standby_zone
    }
  }

  tags = var.tags
}

resource "azurerm_postgresql_flexible_server_database" "sentinel" {
  name      = var.postgres_database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "PGCRYPTO"
}

resource "azurerm_postgresql_flexible_server_active_directory_administrator" "this" {
  count = var.postgres_entra_admin == null ? 0 : 1

  server_name         = azurerm_postgresql_flexible_server.this.name
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id
  object_id           = var.postgres_entra_admin.object_id
  principal_name      = var.postgres_entra_admin.principal_name
  principal_type      = var.postgres_entra_admin.principal_type
}

locals {
  private_endpoints = {
    key_vault = {
      resource_id = azurerm_key_vault.this.id
      subresource = "vault"
      dns_zone_id = var.private_dns_zone_ids["key_vault"]
    }
    blob = {
      resource_id = azurerm_storage_account.application.id
      subresource = "blob"
      dns_zone_id = var.private_dns_zone_ids["blob"]
    }
    acr = {
      resource_id = azurerm_container_registry.this.id
      subresource = "registry"
      dns_zone_id = var.private_dns_zone_ids["acr"]
    }
  }
}

resource "azurerm_private_endpoint" "this" {
  for_each = local.private_endpoints

  name                = "${var.name_prefix}-PE-${upper(replace(each.key, "_", "-"))}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "${var.name_prefix}-PSC-${upper(replace(each.key, "_", "-"))}"
    private_connection_resource_id = each.value.resource_id
    subresource_names              = [each.value.subresource]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [each.value.dns_zone_id]
  }
}

resource "azurerm_role_assignment" "key_vault_secrets" {
  for_each = var.workload_identity_keys

  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.workload_identities[each.key].principal_id
}

resource "azurerm_role_assignment" "identity_blob" {
  for_each = setintersection(var.workload_identity_keys, toset(["identity", "audit", "outbox"]))

  scope                = azurerm_storage_account.application.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.workload_identities[each.key].principal_id
}

resource "azurerm_monitor_diagnostic_setting" "key_vault" {
  name                       = "send-to-log-analytics"
  target_resource_id         = azurerm_key_vault.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "acr" {
  name                       = "send-to-log-analytics"
  target_resource_id         = azurerm_container_registry.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "postgres" {
  name                       = "send-to-log-analytics"
  target_resource_id         = azurerm_postgresql_flexible_server.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_management_lock" "key_vault" {
  count = var.environment == "prod" ? 1 : 0

  name       = "protect-key-vault"
  scope      = azurerm_key_vault.this.id
  lock_level = "CanNotDelete"
}
