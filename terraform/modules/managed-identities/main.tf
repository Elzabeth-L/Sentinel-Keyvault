resource "azurerm_user_assigned_identity" "workload" {
  for_each = var.workloads

  name                = "${var.name_prefix}-ID-${upper(replace(each.key, "_", "-"))}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}
