locals {
  environment     = "prod"
  name_prefix     = "RG-1"
  subscription_id = "a8270be7-dabc-4d92-98db-26a55025b0df"
  tenant_id       = "83474cb5-f1fa-4d06-906c-e5dad12ce3b9"

  tags = merge({
    application         = "sentinel"
    environment         = local.environment
    managed_by          = "terraform"
    repository          = "Elzabeth-L/Sentinel-Keyvault"
    data_classification = "confidential"
    criticality         = "production"
    owner               = var.owner
    cost_center         = var.cost_center
  }, var.additional_tags)

  workloads = {
    web = {
      namespace       = "sentinel-app"
      service_account = "web"
    }
    identity = {
      namespace       = "sentinel-app"
      service_account = "identity-service"
    }
    inventory = {
      namespace       = "sentinel-app"
      service_account = "inventory-service"
    }
    inventory_worker = {
      namespace       = "sentinel-workers"
      service_account = "inventory-worker"
    }
    relationship = {
      namespace       = "sentinel-app"
      service_account = "relationship-service"
    }
    intelligence = {
      namespace       = "sentinel-app"
      service_account = "change-intelligence-service"
    }
    operations = {
      namespace       = "sentinel-app"
      service_account = "operations-service"
    }
    audit = {
      namespace       = "sentinel-app"
      service_account = "audit-service"
    }
    outbox = {
      namespace       = "sentinel-workers"
      service_account = "outbox-relay"
    }
    migration = {
      namespace       = "sentinel-app"
      service_account = "identity-service"
    }
  }
}
