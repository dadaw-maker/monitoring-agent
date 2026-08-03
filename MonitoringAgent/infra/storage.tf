# Azure Files shares mounted into the Prometheus and Grafana container apps.
# Two purposes:
#  - config shares (read-only): monitoring/prometheus/prometheus.yml and
#    monitoring/grafana/provisioning/** are pushed straight from this repo,
#    so the scrape config / dashboards / alert rules in Azure always match
#    what's in git.
#  - the "prometheus-data" share (read-write): Prometheus' actual TSDB, so
#    the historized indicator values survive a Container App revision
#    restart/redeploy — see PROMETHEUS_RETENTION_DAYS / prometheus_retention_days.

resource "azurerm_storage_account" "monitoring" {
  name                           = "st${substr(replace(local.prefix, "-", ""), 0, 14)}${random_id.suffix.hex}"
  resource_group_name            = azurerm_resource_group.this.name
  location                       = azurerm_resource_group.this.location
  account_tier                   = "Standard"
  account_replication_type       = "LRS"
  public_network_access_enabled  = false
  min_tls_version                = "TLS1_2"
  tags                            = local.tags
}

resource "azurerm_private_endpoint" "storage_file" {
  name                = "pe-${local.prefix}-stfile"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-stfile"
    private_connection_resource_id = azurerm_storage_account.monitoring.id
    subresource_names              = ["file"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "stfile-dns"
    private_dns_zone_ids = [azurerm_private_dns_zone.storage_file.id]
  }
}

resource "azurerm_storage_share" "prometheus_config" {
  name                 = "prometheus-config"
  storage_account_name = azurerm_storage_account.monitoring.name
  quota                = 1
}

resource "azurerm_storage_share" "grafana_provisioning" {
  name                 = "grafana-provisioning"
  storage_account_name = azurerm_storage_account.monitoring.name
  quota                = 1
}

# Read-write, unlike the two config shares above — this is where Prometheus
# actually writes its time-series blocks + WAL.
resource "azurerm_storage_share" "prometheus_data" {
  name                 = "prometheus-data"
  storage_account_name = azurerm_storage_account.monitoring.name
  quota                = var.prometheus_storage_quota_gb
}

resource "azurerm_storage_share_file" "prometheus_yml" {
  name             = "prometheus.yml"
  storage_share_id = azurerm_storage_share.prometheus_config.id
  source           = "${path.module}/../monitoring/prometheus/prometheus.yml"
}

locals {
  grafana_provisioning_files = fileset("${path.module}/../monitoring/grafana/provisioning", "**/*")
}

# Azure Files does not auto-create parent directories when uploading a file
# at a nested path — each directory level needs its own resource, created
# before the files that live in it (dashboards/json/ depends on dashboards/).
resource "azurerm_storage_share_directory" "grafana_provisioning_datasources" {
  name             = "datasources"
  storage_share_id = azurerm_storage_share.grafana_provisioning.id
}

resource "azurerm_storage_share_directory" "grafana_provisioning_dashboards" {
  name             = "dashboards"
  storage_share_id = azurerm_storage_share.grafana_provisioning.id
}

resource "azurerm_storage_share_directory" "grafana_provisioning_dashboards_json" {
  name             = "dashboards/json"
  storage_share_id = azurerm_storage_share.grafana_provisioning.id
  depends_on       = [azurerm_storage_share_directory.grafana_provisioning_dashboards]
}

resource "azurerm_storage_share_directory" "grafana_provisioning_alerting" {
  name             = "alerting"
  storage_share_id = azurerm_storage_share.grafana_provisioning.id
}

resource "azurerm_storage_share_file" "grafana_provisioning" {
  for_each         = local.grafana_provisioning_files
  name             = each.value
  storage_share_id = azurerm_storage_share.grafana_provisioning.id
  source           = "${path.module}/../monitoring/grafana/provisioning/${each.value}"

  depends_on = [
    azurerm_storage_share_directory.grafana_provisioning_datasources,
    azurerm_storage_share_directory.grafana_provisioning_dashboards,
    azurerm_storage_share_directory.grafana_provisioning_dashboards_json,
    azurerm_storage_share_directory.grafana_provisioning_alerting,
  ]
}

resource "azurerm_container_app_environment_storage" "prometheus_config" {
  name                         = "prometheus-config"
  container_app_environment_id = azurerm_container_app_environment.this.id
  account_name                 = azurerm_storage_account.monitoring.name
  share_name                   = azurerm_storage_share.prometheus_config.name
  access_key                   = azurerm_storage_account.monitoring.primary_access_key
  access_mode                  = "ReadOnly"
}

resource "azurerm_container_app_environment_storage" "grafana_provisioning" {
  name                         = "grafana-provisioning"
  container_app_environment_id = azurerm_container_app_environment.this.id
  account_name                 = azurerm_storage_account.monitoring.name
  share_name                   = azurerm_storage_share.grafana_provisioning.name
  access_key                   = azurerm_storage_account.monitoring.primary_access_key
  access_mode                  = "ReadOnly"
}

resource "azurerm_container_app_environment_storage" "prometheus_data" {
  name                         = "prometheus-data"
  container_app_environment_id = azurerm_container_app_environment.this.id
  account_name                 = azurerm_storage_account.monitoring.name
  share_name                   = azurerm_storage_share.prometheus_data.name
  access_key                   = azurerm_storage_account.monitoring.primary_access_key
  access_mode                  = "ReadWrite"
}
