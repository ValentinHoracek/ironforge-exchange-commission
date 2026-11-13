resource "azurerm_monitor_action_group" "owner" {
  name                = "ag-ifec-${var.environment}"
  resource_group_name = azurerm_resource_group.platform.name
  short_name          = "ifec${var.environment}"
  tags                = local.tags

  email_receiver {
    name                    = "owner"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

# E-mail when an ingest run fails. The job prints one JSON summary line per run; a failed run
# says "status": "failed". A crash before the summary leaves a Python traceback instead.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "ingest_failed" {
  name                = "alert-ifec-ingest-failed-${var.environment}"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  description         = "An IFEC ingest run failed or crashed. Check the run record in bronze/runs/ and the job logs."
  severity            = 2
  scopes              = [azurerm_log_analytics_workspace.main.id]

  evaluation_frequency = "PT15M"
  window_duration      = "PT30M" # overlaps, so log ingestion delay cannot hide a failure
  # The log table only appears after the first job run; do not validate the query before that.
  skip_query_validation = true

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where Log_s has '"job": "ingest"' and Log_s has '"status": "failed"'
          or Log_s has "Traceback (most recent call last)"
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.owner.id]
  }

  mute_actions_after_alert_duration = "PT1H" # at most one e-mail per hour while it keeps failing
  tags                              = local.tags
}
