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

# --- Resources from infra/data (looked up by name, not managed here) -----------------------

variable "data_resource_group_name" {
  description = "Resource group of infra/data."
  type        = string
}

variable "storage_account_name" {
  description = "Data lake storage account created by infra/data."
  type        = string
}

variable "key_vault_name" {
  description = "Key Vault created by infra/data."
  type        = string
}

# --- Ingest job ------------------------------------------------------------------------------

variable "image_repository" {
  description = "Container image repository of the ingest job."
  type        = string
  default     = "ghcr.io/valentinhoracek/ifec-ingest"
}

variable "image_tag" {
  description = "Exact image tag to deploy: a git commit SHA, never 'latest'."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.image_tag))
    error_message = "image_tag must be a full 40-character git commit SHA."
  }
}

variable "ingest_schedule" {
  description = "Cron schedule (UTC) of the ingest job. Design: poll every 15 minutes."
  type        = string
  default     = "*/15 * * * *"
}

# --- Monitoring ------------------------------------------------------------------------------

variable "alert_email" {
  description = "Where failure alerts go. Set via TF_VAR_alert_email; never stored in git."
  type        = string
  sensitive   = true
}

variable "log_daily_cap_gb" {
  description = "Log Analytics daily ingestion cap (the first 5 GB per month are free)."
  type        = number
  default     = 0.1
}
