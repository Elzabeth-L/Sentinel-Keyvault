resource "azurerm_user_assigned_identity" "control_plane" {
  name                = "${var.name_prefix}-ID-AKS-CONTROL"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_role_assignment" "control_plane_network" {
  scope                = var.aks_subnet_id
  role_definition_name = "Network Contributor"
  principal_id         = azurerm_user_assigned_identity.control_plane.principal_id
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = "${var.name_prefix}-AKS"
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = lower("${var.name_prefix}-aks")
  kubernetes_version  = var.kubernetes_version

  role_based_access_control_enabled = true
  local_account_disabled            = true
  oidc_issuer_enabled               = true
  workload_identity_enabled         = true
  azure_policy_enabled              = true
  sku_tier                          = var.environment == "prod" ? "Standard" : "Free"
  automatic_upgrade_channel         = var.environment == "prod" ? "patch" : "stable"
  node_os_upgrade_channel           = "NodeImage"

  default_node_pool {
    name                         = "system"
    vm_size                      = var.system_pool_vm_size
    vnet_subnet_id               = var.aks_subnet_id
    auto_scaling_enabled         = true
    min_count                    = var.system_pool_min_count
    max_count                    = var.system_pool_max_count
    node_count                   = var.system_pool_min_count
    zones                        = var.availability_zones
    os_disk_type                 = "Managed"
    os_disk_size_gb              = 64
    type                         = "VirtualMachineScaleSets"
    only_critical_addons_enabled = var.user_pool_enabled

    upgrade_settings {
      max_surge = "33%"
    }

    node_labels = {
      "sentinel.vaultrix.in/pool" = var.user_pool_enabled ? "system" : "combined"
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.control_plane.id]
  }

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = var.tenant_id
  }

  api_server_access_profile {
    authorized_ip_ranges = var.api_server_authorized_ip_ranges
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_policy      = "cilium"
    network_data_plane  = "cilium"
    load_balancer_sku   = "standard"
    outbound_type       = "loadBalancer"
    service_cidr        = var.service_cidr
    dns_service_ip      = var.dns_service_ip
    pod_cidr            = var.pod_cidr
  }

  oms_agent {
    log_analytics_workspace_id      = var.log_analytics_workspace_id
    msi_auth_for_monitoring_enabled = true
  }

  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  auto_scaler_profile {
    balance_similar_node_groups      = true
    expander                         = "least-waste"
    max_graceful_termination_sec     = 600
    scale_down_delay_after_add       = "10m"
    scale_down_unneeded              = "10m"
    scale_down_utilization_threshold = "0.5"
    skip_nodes_with_local_storage    = false
  }

  tags = var.tags

  depends_on = [azurerm_role_assignment.control_plane_network]
}

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  count = var.user_pool_enabled ? 1 : 0

  name                  = "user"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.user_pool_vm_size
  vnet_subnet_id        = var.aks_subnet_id
  mode                  = "User"
  auto_scaling_enabled  = true
  min_count             = var.user_pool_min_count
  max_count             = var.user_pool_max_count
  node_count            = var.user_pool_min_count
  zones                 = var.availability_zones
  os_disk_type          = "Managed"
  os_disk_size_gb       = 128

  upgrade_settings {
    max_surge = "33%"
  }

  node_labels = {
    "sentinel.vaultrix.in/pool" = "user"
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = var.container_registry_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
}

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "send-to-log-analytics"
  target_resource_id         = azurerm_kubernetes_cluster.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
