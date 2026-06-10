output "endpoint_id" {
  value = azurerm_cdn_frontdoor_endpoint.this.id
}

output "endpoint_host_name" {
  value = azurerm_cdn_frontdoor_endpoint.this.host_name
}

output "custom_domain_validation_token" {
  value = azurerm_cdn_frontdoor_custom_domain.this.validation_token
}

output "custom_domain_id" {
  value = azurerm_cdn_frontdoor_custom_domain.this.id
}

output "route_id" {
  value = azurerm_cdn_frontdoor_route.this.id
}
