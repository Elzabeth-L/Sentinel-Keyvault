locals {
  tags = {
    application         = "sentinel"
    environment         = "dev"
    managed_by          = "terraform"
    repository          = "Elzabeth-L/Sentinel-Keyvault"
    data_classification = "confidential"
    criticality         = "development"
  }
}

module "state_backend" {
  source = "../../modules/state-backend"

  environment              = "dev"
  location                 = var.location
  resource_group_name      = "DEV-RG-1-TFSTATE"
  storage_account_name     = var.storage_account_name
  allowed_public_ip_ranges = var.allowed_public_ip_ranges
  github_identity_name     = "DEV-RG-1-ID-GITHUB"
  github_environment       = "sentinel-dev"
  github_repository        = var.github_repository
  tags                     = local.tags
}
