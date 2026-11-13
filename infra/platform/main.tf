locals {
  tags = {
    project     = "ifec"
    environment = var.environment
    managed-by  = "terraform"
    tf-root     = "infra/platform"
  }

  # infra/data resources, addressed by ID. Built from names instead of data sources, so this
  # root never reads storage account keys into its state.
  storage_account_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${var.data_resource_group_name}/providers/Microsoft.Storage/storageAccounts/${var.storage_account_name}"
  container_id       = { for c in ["bronze", "serving"] : c => "${local.storage_account_id}/blobServices/default/containers/${c}" }
  secret_names       = ["blizzard-client-id", "blizzard-client-secret"]
}

data "azurerm_client_config" "current" {}

data "azurerm_key_vault" "main" {
  name                = var.key_vault_name
  resource_group_name = var.data_resource_group_name
}

# Everything in this group can be destroyed and rebuilt; the data lives in infra/data.
resource "azurerm_resource_group" "platform" {
  name     = "rg-ifec-${var.environment}"
  location = var.location
  tags     = local.tags
}
