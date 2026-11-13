# Job logs (structured JSON lines). Capped to stay inside the free 5 GB per month.
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-ifec-${var.environment}"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = var.log_daily_cap_gb
  tags                = local.tags
}
