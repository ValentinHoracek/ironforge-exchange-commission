output "resource_group_name" {
  value = azurerm_resource_group.platform.name
}

output "ingest_job_name" {
  value = azurerm_container_app_job.ingest.name
}

output "ingest_identity_client_id" {
  value = azurerm_user_assigned_identity.ingest.client_id
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.main.id
}
