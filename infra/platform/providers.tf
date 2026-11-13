# The subscription ID comes from ARM_SUBSCRIPTION_ID, so it is not stored in this public repo.
provider "azurerm" {
  storage_use_azuread = true
  features {}
}
