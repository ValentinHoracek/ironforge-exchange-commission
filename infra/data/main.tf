locals {
  tags = {
    project     = "ifec"
    environment = var.environment
    managed-by  = "terraform"
    tf-root     = "infra/data"
  }
}

# Long-lived, stateful resources only. Everything that can be rebuilt lives in infra/platform.
resource "azurerm_resource_group" "data" {
  name     = "rg-ifec-${var.environment}-data"
  location = var.location
  tags     = local.tags
}

data "azurerm_client_config" "current" {}
