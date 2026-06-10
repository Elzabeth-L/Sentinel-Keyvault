locals {
  tags = {
    application         = "sentinel"
    environment         = "prod"
    managed_by          = "terraform"
    repository          = "Elzabeth-L/Sentinel-Keyvault"
    data_classification = "confidential"
    criticality         = "production"
  }
}

module "state_backend" {
  source = "../../modules/state-backend"

  environment              = "prod"
  location                 = var.location
  resource_group_name      = "RG-1-TFSTATE"
  storage_account_name     = var.storage_account_name
  allowed_public_ip_ranges = var.allowed_public_ip_ranges
  github_identity_name     = "RG-1-ID-GITHUB"
  github_environment       = "sentinel-prod"
  github_repository        = var.github_repository
  tags                     = local.tags
}
