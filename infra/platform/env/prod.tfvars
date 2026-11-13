# Prod values for infra/platform. Never put secrets or personal data in this file: it is
# committed to a public repo. The alert e-mail comes from TF_VAR_alert_email.
environment = "prod"
location    = "swedencentral"

# From infra/data
data_resource_group_name = "rg-ifec-prod-data"
storage_account_name     = "stifecproda497a1"
key_vault_name           = "kv-ifec-prod-a497a1"

# Exact image to run: the git commit SHA that GitHub Actions built. Set after the first
# image is published; every change of this line is a reviewed deployment.
image_tag = "0000000000000000000000000000000000000000"
