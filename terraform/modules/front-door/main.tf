resource "azurerm_cdn_frontdoor_profile" "this" {
  name                     = "${var.name_prefix}-AFD"
  resource_group_name      = var.resource_group_name
  sku_name                 = "Premium_AzureFrontDoor"
  response_timeout_seconds = 60
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "this" {
  name                     = lower("${var.name_prefix}-afd-endpoint")
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  enabled                  = true
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_origin_group" "this" {
  name                     = "application-gateway"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  session_affinity_enabled = false

  load_balancing {
    sample_size                        = 4
    successful_samples_required        = 3
    additional_latency_in_milliseconds = 50
  }

  health_probe {
    interval_in_seconds = 30
    path                = "/"
    protocol            = "Http"
    request_type        = "HEAD"
  }
}

resource "azurerm_cdn_frontdoor_origin" "this" {
  name                           = "application-gateway"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.this.id
  enabled                        = true
  host_name                      = var.origin_host_name
  origin_host_header             = var.custom_domain
  http_port                      = 80
  https_port                     = 443
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = false
}

resource "azurerm_cdn_frontdoor_custom_domain" "this" {
  name                     = "sentinel-domain"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  host_name                = var.custom_domain

  tls {
    certificate_type = "ManagedCertificate"
  }
}

resource "azurerm_cdn_frontdoor_route" "this" {
  name                            = "sentinel-route"
  cdn_frontdoor_endpoint_id       = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id   = azurerm_cdn_frontdoor_origin_group.this.id
  cdn_frontdoor_origin_ids        = [azurerm_cdn_frontdoor_origin.this.id]
  cdn_frontdoor_custom_domain_ids = [azurerm_cdn_frontdoor_custom_domain.this.id]
  enabled                         = true
  forwarding_protocol             = "HttpOnly"
  https_redirect_enabled          = true
  patterns_to_match               = ["/*"]
  supported_protocols             = ["Http", "Https"]
  link_to_default_domain          = true
}

resource "azurerm_cdn_frontdoor_firewall_policy" "this" {
  name                = replace("${var.name_prefix}AFDWAF", "-", "")
  resource_group_name = var.resource_group_name
  sku_name            = azurerm_cdn_frontdoor_profile.this.sku_name
  enabled             = true
  mode                = "Prevention"
  tags                = var.tags

  custom_rule {
    name     = "AllowOAuthCallback"
    enabled  = true
    priority = 10
    type     = "MatchRule"
    action   = "Allow"

    match_condition {
      match_variable     = "RequestUri"
      operator           = "Contains"
      match_values       = ["/auth/callback"]
      negation_condition = false
      transforms         = ["Lowercase"]
    }
  }

  custom_rule {
    name                           = "RateLimitAuth"
    enabled                        = true
    priority                       = 100
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 100
    type                           = "RateLimitRule"
    action                         = "Block"

    match_condition {
      match_variable     = "RequestUri"
      operator           = "Contains"
      match_values       = ["/auth/", "/api/v1/auth/"]
      negation_condition = false
      transforms         = ["Lowercase"]
    }
  }

  managed_rule {
    type    = "DefaultRuleSet"
    version = "1.0"
    action  = "Block"
  }

  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.0"
    action  = "Block"
  }
}

resource "azurerm_cdn_frontdoor_security_policy" "this" {
  name                     = "sentinel-waf"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.this.id

      association {
        patterns_to_match = ["/*"]

        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_custom_domain.this.id
        }

        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.this.id
        }
      }
    }
  }
}
