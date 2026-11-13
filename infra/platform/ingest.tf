# Serverless home for the jobs: consumption plan, pay per second, nothing runs between jobs.
resource "azurerm_container_app_environment" "main" {
  name                       = "cae-ifec-${var.environment}"
  resource_group_name        = azurerm_resource_group.platform.name
  location                   = azurerm_resource_group.platform.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  logs_destination           = "log-analytics"
  tags                       = local.tags
}

# The ingest job's own Entra identity. It has no password; Azure issues it short-lived tokens.
resource "azurerm_user_assigned_identity" "ingest" {
  name                = "id-ifec-ingest-${var.environment}"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  tags                = local.tags
}

# Least privilege: write only to the bronze and serving containers ...
resource "azurerm_role_assignment" "ingest_storage" {
  for_each = local.container_id

  scope                = each.value
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.ingest.principal_id
  principal_type       = "ServicePrincipal"
}

# ... and read only the two Blizzard secrets, not the whole vault.
resource "azurerm_role_assignment" "ingest_secrets" {
  for_each = toset(local.secret_names)

  scope                = "${data.azurerm_key_vault.main.id}/secrets/${each.key}"
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ingest.principal_id
  principal_type       = "ServicePrincipal"
}

# New role assignments take a while to take effect. Container Apps checks Key Vault access
# when the job is created, so wait before creating it.
resource "time_sleep" "role_propagation" {
  depends_on      = [azurerm_role_assignment.ingest_storage, azurerm_role_assignment.ingest_secrets]
  create_duration = "90s"
}

resource "azurerm_container_app_job" "ingest" {
  name                         = "caj-ifec-ingest-${var.environment}"
  resource_group_name          = azurerm_resource_group.platform.name
  location                     = azurerm_resource_group.platform.location
  container_app_environment_id = azurerm_container_app_environment.main.id

  replica_timeout_in_seconds = 300
  replica_retry_limit        = 0 # the next scheduled run is 15 minutes away; failures alert instead

  schedule_trigger_config {
    cron_expression          = var.ingest_schedule
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.ingest.id]
  }

  # Secret references: Container Apps fetches the values from Key Vault with the job's
  # identity. The values never appear in Terraform state or in this repo.
  dynamic "secret" {
    for_each = toset(local.secret_names)
    content {
      name                = secret.key
      key_vault_secret_id = "${data.azurerm_key_vault.main.vault_uri}secrets/${secret.key}"
      identity            = azurerm_user_assigned_identity.ingest.id
    }
  }

  template {
    container {
      name   = "ingest"
      image  = "${var.image_repository}:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"
      args   = ["--storage-account", var.storage_account_name]

      env {
        name        = "BLIZZARD_CLIENT_ID"
        secret_name = "blizzard-client-id"
      }
      env {
        name        = "BLIZZARD_CLIENT_SECRET"
        secret_name = "blizzard-client-secret"
      }
      env {
        # Tells DefaultAzureCredential which managed identity to use for the data lake.
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.ingest.client_id
      }
    }
  }

  tags = local.tags

  depends_on = [time_sleep.role_propagation]
}
