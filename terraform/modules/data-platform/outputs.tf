output "key_vault_id" {
  value = azurerm_key_vault.this.id
}

output "key_vault_name" {
  value = azurerm_key_vault.this.name
}

output "storage_account_id" {
  value = azurerm_storage_account.application.id
}

output "storage_blob_endpoint" {
  value = azurerm_storage_account.application.primary_blob_endpoint
}

output "container_registry_id" {
  value = azurerm_container_registry.this.id
}

output "container_registry_name" {
  value = azurerm_container_registry.this.name
}

output "container_registry_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}

output "postgres_database_name" {
  value = azurerm_postgresql_flexible_server_database.sentinel.name
}
