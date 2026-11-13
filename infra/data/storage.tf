# Data lake (ADLS Gen2): the single source of truth. Bronze -> Silver -> Gold, plus serving files.
resource "azurerm_storage_account" "lake" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.data.name
  location                 = azurerm_resource_group.data.location
  account_kind             = "StorageV2"
  account_tier             = "Standard"
  account_replication_type = "LRS"
  access_tier              = "Hot"
  is_hns_enabled           = true # hierarchical namespace = ADLS Gen2 (real folders, needed by Delta Lake)

  min_tls_version                  = "TLS1_2"
  https_traffic_only_enabled       = true
  allow_nested_items_to_be_public  = false
  shared_access_key_enabled        = false # no account keys: Entra ID identities only
  default_to_oauth_authentication  = true
  cross_tenant_replication_enabled = false
  local_user_enabled               = false # no SFTP/local accounts: Entra ID is the only way in

  # Accepted risk (see bootstrap/README.md): reachable from the internet because the
  # Container Apps jobs and GitHub-hosted runners have no fixed IPs. Identity is the control.
  public_network_access_enabled = true

  blob_properties {
    # Versioning is not available with a hierarchical namespace; soft delete is the safety net.
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }

  tags = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "layer" {
  for_each = toset(["bronze", "silver", "gold", "serving"])

  name                  = each.key
  storage_account_id    = azurerm_storage_account.lake.id # management plane: works with keys off
  container_access_type = "private"
}

# Retention: Bronze moves to Cold (cheaper, still online) after 6 months. No Archive tier:
# it is offline and would break "rebuild Silver/Gold from Bronze".
resource "azurerm_storage_management_policy" "lake" {
  storage_account_id = azurerm_storage_account.lake.id

  rule {
    name    = "bronze-to-cold"
    enabled = true

    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["bronze/"]
    }

    actions {
      base_blob {
        tier_to_cold_after_days_since_modification_greater_than = var.bronze_cold_after_days
      }
    }
  }
}

# WORM: Bronze blobs cannot be changed or deleted during the retention period.
# Unlocked until the "done" milestone (December 2026). A locked policy can only be extended.
resource "azurerm_storage_container_immutability_policy" "bronze" {
  storage_container_resource_manager_id = azurerm_storage_container.layer["bronze"].id
  immutability_period_in_days           = var.bronze_retention_days
  locked                                = false
  protected_append_writes_all_enabled   = false
}

# The owner can read and write data (laptop tests, ad-hoc queries).
# Reduce to Storage Blob Data Reader in the hardening milestone.
resource "azurerm_role_assignment" "owner_lake" {
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.owner_object_id
  principal_type       = "User"
}
