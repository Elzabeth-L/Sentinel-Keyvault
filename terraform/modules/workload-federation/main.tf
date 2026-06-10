resource "azurerm_federated_identity_credential" "workload" {
  for_each = var.identity_keys

  name                = "fic-${replace(each.key, "_", "-")}"
  resource_group_name = var.resource_group_name
  parent_id           = var.identities[each.key].id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.oidc_issuer_url
  subject             = "system:serviceaccount:${var.identities[each.key].namespace}:${var.identities[each.key].service_account}"
}
