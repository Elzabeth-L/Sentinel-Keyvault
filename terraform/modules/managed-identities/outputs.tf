output "identities" {
  value = {
    for key, identity in azurerm_user_assigned_identity.workload : key => {
      id              = identity.id
      client_id       = identity.client_id
      principal_id    = identity.principal_id
      namespace       = var.workloads[key].namespace
      service_account = var.workloads[key].service_account
    }
  }
}
