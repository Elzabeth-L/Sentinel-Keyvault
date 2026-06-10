resource "azurerm_dns_zone" "this" {
  name                = var.zone_name
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_dns_a_record" "production" {
  name                = "@"
  zone_name           = azurerm_dns_zone.this.name
  resource_group_name = var.resource_group_name
  ttl                 = 300
  target_resource_id  = var.frontdoor_endpoint_id
  tags                = var.tags
}

resource "azurerm_dns_txt_record" "frontdoor_validation" {
  name                = "_dnsauth"
  zone_name           = azurerm_dns_zone.this.name
  resource_group_name = var.resource_group_name
  ttl                 = 300
  tags                = var.tags

  record {
    value = var.frontdoor_validation_token
  }
}

resource "azurerm_dns_a_record" "development" {
  count = var.dev_application_gateway_ip == null ? 0 : 1

  name                = "dev"
  zone_name           = azurerm_dns_zone.this.name
  resource_group_name = var.resource_group_name
  ttl                 = 300
  records             = [var.dev_application_gateway_ip]
  tags                = var.tags
}
