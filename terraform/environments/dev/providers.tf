provider "azurerm" {
  subscription_id     = local.subscription_id
  tenant_id           = local.tenant_id
  storage_use_azuread = true

  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}
