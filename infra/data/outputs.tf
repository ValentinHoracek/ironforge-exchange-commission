output "resource_group_name" {
  value = azurerm_resource_group.data.name
}

output "storage_account_id" {
  value = azurerm_storage_account.lake.id
}

output "storage_account_name" {
  value = azurerm_storage_account.lake.name
}

output "storage_blob_endpoint" {
  value = azurerm_storage_account.lake.primary_blob_endpoint
}

output "container_ids" {
  description = "Resource Manager IDs of the containers, used to scope job role assignments."
  value       = { for name, c in azurerm_storage_container.layer : name => c.id }
}

output "key_vault_id" {
  value = azurerm_key_vault.main.id
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}
