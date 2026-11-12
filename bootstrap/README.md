# Bootstrap – manual steps

Everything in IFEC is created by Terraform from GitHub Actions, with one exception: the steps on this page.
They are the **only allowed manual changes** ("click-ops"), because they must exist before Terraform can run
(an account to deploy into, credentials, and a place for Terraform to store its state).

Each step records **what** was done, **why**, **how** (exact commands), and **how it was verified**.
Identifiers that are not needed to reproduce the setup (subscription ID, tenant ID, object IDs, e-mail
addresses) are left out on purpose, because this repository is public.

| # | Step | Date | Status |
|---|---|---|---|
| 1 | Blizzard developer account and API client | 2026-11-06 | ✅ |
| 2 | Azure subscription `ifec` | 2026-11-10 | ✅ |
| 3 | Resource providers registered | 2026-11-10 | ✅ |
| 4 | Budget `budget-ifec-monthly` | 2026-11-10 | ✅ |
| 5 | Terraform state storage | 2026-11-12 | ✅ |
| 6 | GitHub → Azure OIDC (app registration + federated credentials) | – | planned (milestone 2) |

---

## 1. Blizzard developer account and API client

- **What:** an API client at [develop.battle.net](https://develop.battle.net) (free).
- **Why:** the ingest job reads auction house data from the Blizzard Game Data API with an OAuth client-credentials token.
- **Secret handling:** the client ID and secret are kept outside the repository. They move into Azure Key Vault
  when Terraform creates it; the secret value is then set by CLI, so it never appears in Terraform state or in git.

## 2. Azure subscription

- **What:** a dedicated subscription named `ifec` in its own Entra ID tenant. The owner has the Owner role on the
  subscription and is Global Administrator of the tenant.
- **Why dedicated:** budgets, cost panels and RBAC can be scoped to the whole subscription without mixing in other workloads.
- **Identity baseline:** Entra ID **security defaults** are enabled (MFA required, legacy authentication blocked).
  On 2026-11-12 they blocked an Azure CLI session whose token lacked an MFA claim (`AADSTS530035`); a fresh
  `az login` with MFA resolved it. This is the control working as intended.
- **Note:** the subscription started as a Free Trial. It must be upgraded to pay-as-you-go before the trial ends,
  otherwise Azure disables its resources and ingestion stops.

## 3. Resource providers

- **What:** registered `Microsoft.App`, `Microsoft.Storage`, `Microsoft.KeyVault`, `Microsoft.OperationalInsights`,
  `Microsoft.Insights`, `Microsoft.ManagedIdentity` (`Microsoft.CostManagement` and `Microsoft.Consumption` were already registered).
- **Why:** a new subscription cannot create a resource type until its provider is registered. Registering them once up
  front avoids failed first Terraform applies.

```bash
for p in Microsoft.App Microsoft.Storage Microsoft.KeyVault Microsoft.OperationalInsights Microsoft.Insights Microsoft.ManagedIdentity; do
  az provider register --namespace "$p"
done
az provider list --query "[?registrationState=='Registered'].namespace" -o table
```

## 4. Budget

- **What:** `budget-ifec-monthly` on the `ifec` subscription: **€15/month** (EUR is the billing currency), monthly reset,
  expires 2029-10-31. E-mail alerts to the owner at 50 / 80 / 100 % of actual cost and 100 % of forecasted cost.
- **Why:** the project has a hard cost cap. Cost data lags by ~8–24 h, so this is a **detective** control, not a preventive one.
- **Later:** Terraform will **import** this budget (not create a second one), so from then on it is managed as code.

## 5. Terraform state storage

- **What:** resource group `rg-ifec-tfstate` and storage account `stifectfstate6ca2f7` with container `tfstate`,
  in Sweden Central.
- **Why manual:** Terraform keeps its state (its record of what it has built) in this account. Terraform cannot create
  the storage that holds its own state, so this one account is created by hand. It lives in its own resource group so it
  survives the deletion of any IFEC environment.

### Commands

Run in one shell session (the variables are reused).

```bash
# 0. Check the active subscription
az account show --query "{subscription:name, user:user.name}" -o table   # expect: ifec

# 1. Variables (the storage account name must be globally unique, 3-24 lowercase letters/digits)
LOCATION=swedencentral
RG=rg-ifec-tfstate
SA=stifectfstate$(openssl rand -hex 3)      # result used: stifectfstate6ca2f7
az storage account check-name --name $SA -o table

# 2. Resource group
az group create --name $RG --location $LOCATION \
  --tags project=ifec purpose=terraform-state managed-by=manual-bootstrap

# 3. Storage account
az storage account create \
  --name $SA --resource-group $RG --location $LOCATION \
  --sku Standard_LRS --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --https-only true \
  --allow-blob-public-access false \
  --allow-shared-key-access false \
  --tags project=ifec purpose=terraform-state managed-by=manual-bootstrap

# 4. Versioning and soft delete
az storage account blob-service-properties update \
  --account-name $SA --resource-group $RG \
  --enable-versioning true \
  --enable-delete-retention true --delete-retention-days 30 \
  --enable-container-delete-retention true --container-delete-retention-days 30

# 5. Delete lock
az lock create --name lock-tfstate-nodelete --resource-group $RG \
  --lock-type CanNotDelete --notes "Terraform state - do not delete"

# 6. Data-plane access for the signed-in user
ME=$(az ad signed-in-user show --query id -o tsv)
SA_ID=$(az storage account show -n $SA -g $RG --query id -o tsv)
az role assignment create --assignee-object-id $ME --assignee-principal-type User \
  --role "Storage Blob Data Contributor" --scope $SA_ID

# 7. State container (retry after a few minutes if it returns 403 – role assignments take time to propagate)
az storage container create --name tfstate --account-name $SA --auth-mode login
```

### Settings and why

| Setting | Value | Why |
|---|---|---|
| Redundancy | `Standard_LRS` | State files are tiny; cost is cents per year. Recovery relies on versioning, not geo-replication |
| Minimum TLS / HTTPS only | TLS 1.2 / yes | Encrypted transport only |
| Public blob access | off | No container can be made anonymous, even by mistake |
| Shared key access | **off** | No account keys (master passwords). Access only through Entra ID identities, which are logged and revocable. Terraform's backend uses `use_azuread_auth = true` |
| Hierarchical namespace | off | Blob versioning is not supported with it |
| Blob versioning | on | Restore the previous state if an apply corrupts it |
| Soft delete (blobs, containers) | 30 days | Recover a deleted state file or container |
| Resource lock | `CanNotDelete` on the resource group | Even an Owner must remove the lock deliberately before deleting |
| RBAC | `Storage Blob Data Contributor` for the owner, scoped to this account | The Owner role manages the account (control plane) but cannot read blobs (data plane). With keys off, a data role is required |

### Accepted risk

- **Public network access is enabled** (`networkRuleSet.defaultAction = Allow`). GitHub-hosted runners use changing
  IP addresses, so an IP firewall would block the pipeline. The compensating control is identity: shared keys are
  off and only Entra identities with a data-plane role can read or write. Revisit if self-hosted runners or private
  endpoints are introduced.

### Verification (2026-11-12)

```bash
az storage account show -n $SA -g $RG -o table \
  --query "{tls:minimumTlsVersion, publicBlob:allowBlobPublicAccess, sharedKey:allowSharedKeyAccess, httpsOnly:enableHttpsTrafficOnly}"
az storage account blob-service-properties show --account-name $SA -g $RG -o table \
  --query "{versioning:isVersioningEnabled, blobSoftDelete:deleteRetentionPolicy.days, containerSoftDelete:containerDeleteRetentionPolicy.days}"
az lock list -g $RG -o table
az storage container list --account-name $SA --auth-mode login -o table
```

Result: `TLS1_2 / False / False / True`, versioning `True`, soft delete `30 / 30`, lock `CanNotDelete`, container `tfstate` present.

**Activity log** (resource group `rg-ifec-tfstate`) shows the control-plane operations: create resource group, create
storage account, put blob service properties, create management lock, create role assignment. Container creation is a
data-plane operation and does not appear there.
