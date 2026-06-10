output "vnet_id" {
  value = azurerm_virtual_network.this.id
}

output "subnet_ids" {
  value = {
    app_gateway       = azurerm_subnet.app_gateway.id
    aks               = azurerm_subnet.aks.id
    private_endpoints = azurerm_subnet.private_endpoints.id
    postgresql        = azurerm_subnet.postgresql.id
  }
}

output "private_dns_zone_ids" {
  value = { for key, zone in azurerm_private_dns_zone.this : key => zone.id }
}

output "private_dns_zone_names" {
  value = { for key, zone in azurerm_private_dns_zone.this : key => zone.name }
}
