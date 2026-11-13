# Where Terraform keeps the state of infra/data for prod (created in bootstrap, step 5).
resource_group_name  = "rg-ifec-tfstate"
storage_account_name = "stifectfstate6ca2f7"
container_name       = "tfstate"
key                  = "prod/data.tfstate"
use_azuread_auth     = true
