resource "azurerm_log_analytics_workspace" "this" {
  name                = "${var.name_prefix}-LAW"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.environment == "prod" ? 90 : 30
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = "${var.name_prefix}-APPINSIGHTS"
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  tags                = var.tags
}

resource "azurerm_monitor_action_group" "this" {
  name                = "${var.name_prefix}-AG-PLATFORM"
  resource_group_name = var.resource_group_name
  short_name          = substr(replace(lower(var.name_prefix), "-", ""), 0, 12)
  tags                = var.tags

  dynamic "email_receiver" {
    for_each = var.alert_email == null ? [] : [var.alert_email]

    content {
      name          = "platform-owner"
      email_address = email_receiver.value
    }
  }
}
