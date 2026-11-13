# Secrets for the jobs (Blizzard client ID and secret). Terraform creates the vault only:
# secret values are set by the owner with the Azure CLI, so they never appear in state or git.
resource "azurerm_key_vault" "main" {
  name                       = var.key_vault_name
  resource_group_name        = azurerm_resource_group.data.name
  location                   = azurerm_resource_group.data.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true # access through Azure RBAC roles, not legacy access policies
  purge_protection_enabled   = true
  soft_delete_retention_days = var.key_vault_soft_delete_days

  # Same accepted risk as the storage account: no fixed IPs for the jobs.
  public_network_access_enabled = true

  tags = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

# The Owner role manages the vault (control plane) but cannot read or write secrets (data plane).
resource "azurerm_role_assignment" "owner_kv_secrets" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.owner_object_id
  principal_type       = "User"
}
