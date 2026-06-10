output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "aks_name" {
  value = module.aks.name
}

output "frontdoor_endpoint" {
  value = module.front_door.endpoint_host_name
}

output "azure_dns_name_servers" {
  value = module.dns.name_servers
}

output "application_gateway_public_ip" {
  value = module.application_gateway.public_ip_address
}

output "acr" {
  value = {
    name         = module.data_platform.container_registry_name
    login_server = module.data_platform.container_registry_login_server
  }
}

output "key_vault_name" {
  value = module.data_platform.key_vault_name
}

output "postgres_fqdn" {
  value = module.data_platform.postgres_fqdn
}

output "workload_identity_client_ids" {
  value = { for key, identity in module.identities.identities : key => identity.client_id }
}
