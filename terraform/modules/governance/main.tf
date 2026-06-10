resource "azurerm_policy_definition" "allowed_locations" {
  name         = lower("${var.name_prefix}-allowed-locations")
  policy_type  = "Custom"
  mode         = "Indexed"
  display_name = "${var.name_prefix}: allowed Azure regions"

  metadata = jsonencode({
    category = "Sentinel"
  })

  policy_rule = jsonencode({
    if = {
      allOf = [
        {
          field = "location"
          notIn = var.allowed_locations
        },
        {
          field     = "location"
          notEquals = "global"
        }
      ]
    }
    then = {
      effect = "deny"
    }
  })
}

resource "azurerm_subscription_policy_assignment" "allowed_locations" {
  name                 = lower("${var.name_prefix}-allowed-locations")
  subscription_id      = "/subscriptions/${var.subscription_id}"
  policy_definition_id = azurerm_policy_definition.allowed_locations.id
  display_name         = "${var.name_prefix}: restrict Azure regions"
}

resource "azurerm_policy_definition" "required_tags" {
  for_each = toset(var.required_tags)

  name         = lower("${var.name_prefix}-audit-tag-${replace(each.value, "_", "-")}")
  policy_type  = "Custom"
  mode         = "Indexed"
  display_name = "${var.name_prefix}: audit required tag ${each.value}"

  metadata = jsonencode({
    category = "Sentinel"
  })

  policy_rule = jsonencode({
    if = {
      field  = "tags['${each.value}']"
      exists = "false"
    }
    then = {
      effect = "audit"
    }
  })
}

resource "azurerm_subscription_policy_assignment" "required_tags" {
  for_each = toset(var.required_tags)

  name                 = lower("${var.name_prefix}-audit-tag-${replace(each.key, "_", "-")}")
  subscription_id      = "/subscriptions/${var.subscription_id}"
  policy_definition_id = azurerm_policy_definition.required_tags[each.key].id
  display_name         = "${var.name_prefix}: audit tag ${each.key}"
}
