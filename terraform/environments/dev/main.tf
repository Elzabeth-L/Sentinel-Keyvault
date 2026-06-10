resource "azurerm_resource_group" "this" {
  name     = "DEV-RG-1"
  location = var.location
  tags     = local.tags
}

module "governance" {
  source = "../../modules/governance"

  name_prefix       = local.name_prefix
  subscription_id   = local.subscription_id
  allowed_locations = [var.location]
  required_tags     = ["application", "environment", "managed_by", "owner", "cost_center"]
}

module "network" {
  source = "../../modules/network"

  name_prefix         = local.name_prefix
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  vnet_address_space  = ["10.20.0.0/16"]
  subnet_prefixes = {
    aks               = "10.20.8.0/21"
    private_endpoints = "10.20.20.0/24"
    app_gateway       = "10.20.30.0/24"
    postgresql        = "10.20.40.0/24"
  }
  tags = local.tags
}

module "monitoring" {
  source = "../../modules/monitoring"

  name_prefix         = local.name_prefix
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  environment         = local.environment
  alert_email         = var.alert_email
  tags                = local.tags
}

module "identities" {
  source = "../../modules/managed-identities"

  name_prefix         = local.name_prefix
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  workloads           = local.workloads
  tags                = local.tags
}

module "data_platform" {
  source = "../../modules/data-platform"

  name_prefix                    = local.name_prefix
  environment                    = local.environment
  resource_group_name            = azurerm_resource_group.this.name
  location                       = var.location
  tenant_id                      = local.tenant_id
  key_vault_name                 = "devrg1kv${var.name_suffix}"
  storage_account_name           = "devrg1st${var.name_suffix}"
  container_registry_name        = "devrg1acr${var.name_suffix}"
  postgres_server_name           = "dev-rg-1-pg-${var.name_suffix}"
  postgres_admin_password        = var.postgres_admin_password
  postgres_sku_name              = "B_Standard_B2ms"
  postgres_storage_mb            = 32768
  postgres_backup_retention_days = 7
  postgres_entra_admin           = var.postgres_entra_admin
  private_endpoint_subnet_id     = module.network.subnet_ids.private_endpoints
  postgres_subnet_id             = module.network.subnet_ids.postgresql
  private_dns_zone_ids           = module.network.private_dns_zone_ids
  log_analytics_workspace_id     = module.monitoring.log_analytics_workspace_id
  workload_identities            = module.identities.identities
  workload_identity_keys         = toset(keys(local.workloads))
  tags                           = local.tags
}

module "aks" {
  source = "../../modules/aks"

  name_prefix                     = local.name_prefix
  environment                     = local.environment
  resource_group_name             = azurerm_resource_group.this.name
  location                        = var.location
  tenant_id                       = local.tenant_id
  aks_subnet_id                   = module.network.subnet_ids.aks
  log_analytics_workspace_id      = module.monitoring.log_analytics_workspace_id
  container_registry_id           = module.data_platform.container_registry_id
  api_server_authorized_ip_ranges = var.operator_and_ci_cidrs
  system_pool_vm_size             = "Standard_D2as_v5"
  system_pool_min_count           = 1
  system_pool_max_count           = 3
  user_pool_enabled               = false
  user_pool_vm_size               = "Standard_D2as_v5"
  user_pool_min_count             = 0
  user_pool_max_count             = 0
  availability_zones              = []
  service_cidr                    = "10.21.0.0/16"
  dns_service_ip                  = "10.21.0.10"
  pod_cidr                        = "10.244.0.0/16"
  tags                            = local.tags
}

module "workload_federation" {
  source = "../../modules/workload-federation"

  resource_group_name = azurerm_resource_group.this.name
  oidc_issuer_url     = module.aks.oidc_issuer_url
  identities          = module.identities.identities
  identity_keys       = toset(keys(local.workloads))
}

module "application_gateway" {
  source = "../../modules/application-gateway"

  name_prefix                = local.name_prefix
  environment                = local.environment
  resource_group_name        = azurerm_resource_group.this.name
  location                   = var.location
  subnet_id                  = module.network.subnet_ids.app_gateway
  backend_ip_address         = "10.20.8.10"
  custom_domain              = "dev.sentinel.vaultrix.in"
  certificate_secret_id      = var.gateway_certificate_secret_id
  key_vault_id               = module.data_platform.key_vault_id
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  zones                      = []
  tags                       = local.tags
}
