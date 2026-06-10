resource "azurerm_resource_group" "this" {
  name     = "RG-1"
  location = var.location
  tags     = local.tags
}

module "governance" {
  source = "../../modules/governance"

  name_prefix       = local.name_prefix
  subscription_id   = local.subscription_id
  allowed_locations = [var.location, "global"]
  required_tags     = ["application", "environment", "managed_by", "owner", "cost_center"]
}

module "network" {
  source = "../../modules/network"

  name_prefix         = local.name_prefix
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  vnet_address_space  = ["10.10.0.0/16"]
  subnet_prefixes = {
    aks               = "10.10.8.0/21"
    private_endpoints = "10.10.20.0/24"
    app_gateway       = "10.10.30.0/24"
    postgresql        = "10.10.40.0/24"
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

  name_prefix                           = local.name_prefix
  environment                           = local.environment
  resource_group_name                   = azurerm_resource_group.this.name
  location                              = var.location
  tenant_id                             = local.tenant_id
  key_vault_name                        = "RG-1-KV"
  storage_account_name                  = "rg1st${var.name_suffix}"
  container_registry_name               = "rg1acr${var.name_suffix}"
  postgres_server_name                  = "rg-1-pg-${var.name_suffix}"
  postgres_admin_password               = var.postgres_admin_password
  postgres_sku_name                     = "GP_Standard_D2ds_v5"
  postgres_storage_mb                   = 65536
  postgres_backup_retention_days        = 35
  postgres_geo_redundant_backup_enabled = true
  postgres_zone                         = "1"
  postgres_ha_enabled                   = true
  postgres_ha_standby_zone              = "2"
  postgres_entra_admin                  = var.postgres_entra_admin
  private_endpoint_subnet_id            = module.network.subnet_ids.private_endpoints
  postgres_subnet_id                    = module.network.subnet_ids.postgresql
  private_dns_zone_ids                  = module.network.private_dns_zone_ids
  log_analytics_workspace_id            = module.monitoring.log_analytics_workspace_id
  workload_identities                   = module.identities.identities
  workload_identity_keys                = toset(keys(local.workloads))
  tags                                  = local.tags
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
  system_pool_vm_size             = "Standard_D2s_v3"
  system_pool_min_count           = 1
  system_pool_max_count           = 3
  user_pool_enabled               = true
  user_pool_vm_size               = "Standard_D2s_v3"
  user_pool_min_count             = 1
  user_pool_max_count             = 3
  availability_zones              = []
  service_cidr                    = "10.11.0.0/16"
  dns_service_ip                  = "10.11.0.10"
  pod_cidr                        = "10.242.0.0/16"
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
  backend_ip_address         = "10.10.8.10"
  custom_domain              = "sentinel.vaultrix.in"
  certificate_secret_id      = var.gateway_certificate_secret_id
  key_vault_id               = module.data_platform.key_vault_id
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  zones                      = ["1", "2"]
  tags                       = local.tags
}

module "front_door" {
  source = "../../modules/front-door"

  name_prefix         = local.name_prefix
  resource_group_name = azurerm_resource_group.this.name
  origin_host_name    = module.application_gateway.public_fqdn
  custom_domain       = "sentinel.vaultrix.in"
  tags                = local.tags
}

module "dns" {
  source = "../../modules/dns"

  resource_group_name        = azurerm_resource_group.this.name
  zone_name                  = "sentinel.vaultrix.in"
  frontdoor_endpoint_id      = module.front_door.endpoint_id
  frontdoor_validation_token = module.front_door.custom_domain_validation_token
  dev_application_gateway_ip = var.dev_application_gateway_ip
  tags                       = local.tags
}

resource "azurerm_management_lock" "resource_group" {
  name       = "protect-production-resources"
  scope      = azurerm_resource_group.this.id
  lock_level = "CanNotDelete"

  depends_on = [
    module.aks,
    module.application_gateway,
    module.data_platform,
    module.dns,
    module.front_door,
    module.governance,
    module.identities,
    module.monitoring,
    module.network,
    module.workload_federation,
  ]
}
