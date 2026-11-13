variable "environment" {
  description = "Environment name (dev or prod)."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "swedencentral"
}

variable "storage_account_name" {
  description = "Data lake storage account name (globally unique, 3-24 lowercase letters and digits)."
  type        = string
}

variable "key_vault_name" {
  description = "Key Vault name (globally unique, 3-24 characters)."
  type        = string
}

variable "key_vault_soft_delete_days" {
  description = "Days a deleted vault or secret stays recoverable (7-90). Purge protection blocks early deletion."
  type        = number
  default     = 90
}

variable "bronze_cold_after_days" {
  description = "Move Bronze blobs to the Cold tier after this many days (design: 6 months)."
  type        = number
  default     = 180
}

variable "bronze_retention_days" {
  description = "WORM retention for the bronze container: blobs cannot be changed or deleted for this many days."
  type        = number
  default     = 365
}

variable "owner_object_id" {
  description = "Entra object ID of the human owner. Set via TF_VAR_owner_object_id, not stored in git."
  type        = string
}
