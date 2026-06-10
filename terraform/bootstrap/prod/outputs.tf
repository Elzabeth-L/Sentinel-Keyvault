output "backend" {
  value = {
    resource_group_name  = module.state_backend.resource_group_name
    storage_account_name = module.state_backend.storage_account_name
    container_name       = module.state_backend.container_name
    key                  = "sentinel-prod.tfstate"
  }
}

output "github_client_id" {
  value = module.state_backend.github_client_id
}
