data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "state" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_account" "state" {
  name                             = var.storage_account_name
  resource_group_name              = azurerm_resource_group.state.name
  location                         = azurerm_resource_group.state.location
  account_tier                     = "Standard"
  account_replication_type         = var.environment == "prod" ? "ZRS" : "LRS"
  account_kind                     = "StorageV2"
  min_tls_version                  = "TLS1_2"
  public_network_access_enabled    = true
  allow_nested_items_to_be_public  = false
  shared_access_key_enabled        = false
  default_to_oauth_authentication  = true
  cross_tenant_replication_enabled = false

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
    default_action = length(var.allowed_public_ip_ranges) > 0 ? "Deny" : "Allow"
    bypass         = ["AzureServices"]
    ip_rules       = var.allowed_public_ip_ranges
  }

  tags = var.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "state" {
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

resource "azurerm_user_assigned_identity" "github" {
  name                = var.github_identity_name
  location            = azurerm_resource_group.state.location
  resource_group_name = azurerm_resource_group.state.name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "github" {
  name                = "github-${var.environment}"
  resource_group_name = azurerm_resource_group.state.name
  parent_id           = azurerm_user_assigned_identity.github.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repository}:environment:${var.github_environment}"
}

resource "azurerm_role_assignment" "state_blob" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}

resource "azurerm_role_assignment" "subscription_contributor" {
  count = var.assign_subscription_deployment_roles ? 1 : 0

  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}

resource "azurerm_role_assignment" "subscription_rbac" {
  count = var.assign_subscription_deployment_roles ? 1 : 0

  scope                = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}

resource "azurerm_management_lock" "state" {
  count = var.environment == "prod" ? 1 : 0

  name       = "protect-terraform-state"
  scope      = azurerm_storage_account.state.id
  lock_level = "CanNotDelete"
  notes      = "Production Terraform state must not be deleted during workload cleanup."
}
