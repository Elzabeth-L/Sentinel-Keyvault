resource "azurerm_public_ip" "this" {
  name                = "${var.name_prefix}-PIP-APPGW"
  resource_group_name = var.resource_group_name
  location            = var.location
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = var.zones
  domain_name_label   = lower(replace("${var.name_prefix}-appgw", "_", "-"))
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "this" {
  name                = "${var.name_prefix}-ID-APPGW"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "certificate" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}

resource "azurerm_web_application_firewall_policy" "this" {
  name                = "${var.name_prefix}-WAF-APPGW"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags

  custom_rules {
    name      = "AllowOAuthCallback"
    priority  = 10
    rule_type = "MatchRule"
    action    = "Allow"

    match_conditions {
      match_variables {
        variable_name = "RequestUri"
      }

      operator           = "Contains"
      negation_condition = false
      match_values       = ["/auth/callback"]
      transforms         = ["Lowercase"]
    }
  }

  policy_settings {
    enabled                     = true
    mode                        = var.environment == "prod" ? "Prevention" : "Detection"
    request_body_check          = true
    max_request_body_size_in_kb = 128
    file_upload_limit_in_mb     = 10
  }

  managed_rules {
    exclusion {
      match_variable          = "RequestArgNames"
      selector                = "code"
      selector_match_operator = "Equals"
    }

    managed_rule_set {
      type    = "OWASP"
      version = "3.2"
    }
  }
}

locals {
  gateway_ip_configuration_name = "gateway-ip"
  frontend_ip_name              = "public-frontend"
  frontend_http_port_name       = "frontend-http"
  frontend_https_port_name      = "frontend-https"
  backend_pool_name             = "aks-ingress"
  backend_settings_name         = "aks-ingress-settings"
  probe_name                    = "aks-ingress-probe"
  listener_name                 = var.certificate_secret_id == null ? "http-listener" : "https-listener"
  routing_rule_name             = "sentinel-route"
}

resource "azurerm_application_gateway" "this" {
  name                = "${var.name_prefix}-APPGW"
  resource_group_name = var.resource_group_name
  location            = var.location
  firewall_policy_id  = azurerm_web_application_firewall_policy.this.id
  zones               = var.zones
  tags                = var.tags

  autoscale_configuration {
    min_capacity = var.environment == "prod" ? 2 : 1
    max_capacity = var.environment == "prod" ? 10 : 2
  }

  sku {
    name = "WAF_v2"
    tier = "WAF_v2"
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  gateway_ip_configuration {
    name      = local.gateway_ip_configuration_name
    subnet_id = var.subnet_id
  }

  frontend_ip_configuration {
    name                 = local.frontend_ip_name
    public_ip_address_id = azurerm_public_ip.this.id
  }

  frontend_port {
    name = local.frontend_http_port_name
    port = 80
  }

  frontend_port {
    name = local.frontend_https_port_name
    port = 443
  }

  backend_address_pool {
    name         = local.backend_pool_name
    ip_addresses = [var.backend_ip_address]
  }

  probe {
    name                                      = local.probe_name
    protocol                                  = var.backend_protocol
    path                                      = "/"
    interval                                  = 30
    timeout                                   = 10
    unhealthy_threshold                       = 3
    pick_host_name_from_backend_http_settings = false
    host                                      = var.custom_domain
  }

  backend_http_settings {
    name                  = local.backend_settings_name
    protocol              = var.backend_protocol
    port                  = var.backend_port
    cookie_based_affinity = "Disabled"
    request_timeout       = 30
    probe_name            = local.probe_name
    host_name             = var.custom_domain
  }

  dynamic "ssl_certificate" {
    for_each = var.certificate_secret_id == null ? [] : [var.certificate_secret_id]

    content {
      name                = "sentinel-certificate"
      key_vault_secret_id = ssl_certificate.value
    }
  }

  http_listener {
    name                           = local.listener_name
    frontend_ip_configuration_name = local.frontend_ip_name
    frontend_port_name             = var.certificate_secret_id == null ? local.frontend_http_port_name : local.frontend_https_port_name
    protocol                       = var.certificate_secret_id == null ? "Http" : "Https"
    ssl_certificate_name           = var.certificate_secret_id == null ? null : "sentinel-certificate"
    host_name                      = var.custom_domain
    require_sni                    = var.certificate_secret_id != null
  }

  request_routing_rule {
    name                       = local.routing_rule_name
    rule_type                  = "Basic"
    http_listener_name         = local.listener_name
    backend_address_pool_name  = local.backend_pool_name
    backend_http_settings_name = local.backend_settings_name
    priority                   = 100
  }

  depends_on = [azurerm_role_assignment.certificate]
}

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "send-to-log-analytics"
  target_resource_id         = azurerm_application_gateway.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
