# The subscription ID comes from ARM_SUBSCRIPTION_ID, so it is not stored in this public repo.
provider "azurerm" {
  # Shared keys are disabled on IFEC storage accounts; use Entra ID for data-plane calls.
  storage_use_azuread = true

  features {
    key_vault {
      # Never purge a vault or secret on destroy: soft delete + purge protection must hold.
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}
