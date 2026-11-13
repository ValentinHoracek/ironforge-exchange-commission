terraform {
  required_version = "~> 1.17"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # Partial configuration: the environment's state file is chosen at init time,
  # e.g. terraform init -backend-config=env/prod.backend.hcl
  backend "azurerm" {}
}
