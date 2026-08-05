# Azure Container Apps environment + the four Azure-hosted services
# (specs.md §9.1). mcp_gold is NOT here: it runs on-premises in the
# LabelVie datacenter, reached through the VPN configured in network.tf.
#
# Ingress is internal-only for everything except Grafana (specs.md §9.4
# "cloisonnement réseau" — only the dashboard needs to be reachable by
# people outside the platform).

resource "azurerm_container_app_environment" "this" {
  name                            = "cae-${local.prefix}"
  location                        = azurerm_resource_group.this.location
  resource_group_name             = azurerm_resource_group.this.name
  log_analytics_workspace_id      = azurerm_log_analytics_workspace.this.id
  infrastructure_subnet_id        = azurerm_subnet.aca.id
  internal_load_balancer_enabled  = false
  tags                             = local.tags
}

# --------------------------------------------------------------------------
# mcp-relex-generix
# --------------------------------------------------------------------------

resource "azurerm_container_app" "mcp_relex_generix" {
  name                         = "ca-${local.prefix}-relex-generix" # "mcp-" dropped: Azure Container App names are capped at 32 chars
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  tags                          = local.tags

  depends_on = [time_sleep.wait_for_kv_rbac] # let the Key Vault Secrets User grant propagate first

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.mcp_relex_generix.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.mcp_relex_generix.id
  }

  # TEMPORARY: Container Apps' Key Vault secret reference resolution
  # ("Unable to get value using Managed identity ... timeout after 5s")
  # fails consistently despite confirmed-correct RBAC (Key Vault Secrets
  # User on this identity) and network access (Enabled, All Networks) —
  # see azure-deployment.md for the full diagnostic trail. Using literal
  # values here as an unblock (all current values are non-sensitive
  # placeholders — "changeme"/stub credentials, see variables.tf defaults)
  # until the root cause is found. Revert to key_vault_secret_id + identity
  # once real credentials are in play.
  secret {
    name  = "relex-client-id"
    value = var.relex_client_id
  }
  secret {
    name  = "relex-client-secret"
    value = var.relex_client_secret
  }
  secret {
    name  = "relex-api-key"
    value = var.relex_api_key
  }
  secret {
    name  = "generix-api-key"
    value = var.generix_api_key
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "mcp-relex-generix"
      image  = "${azurerm_container_registry.this.login_server}/mcp-relex-generix:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "RELEX_MODE"
        value = var.relex_mode
      }
      env {
        name  = "GENERIX_MODE"
        value = var.generix_mode
      }
      env {
        name        = "RELEX_CLIENT_ID"
        secret_name = "relex-client-id"
      }
      env {
        name        = "RELEX_CLIENT_SECRET"
        secret_name = "relex-client-secret"
      }
      env {
        name        = "RELEX_API_KEY"
        secret_name = "relex-api-key"
      }
      env {
        name        = "GENERIX_API_KEY"
        secret_name = "generix-api-key"
      }
    }
  }

  ingress {
    external_enabled = false
    target_port       = 8002
    transport          = "http"

    traffic_weight {
      latest_revision = true
      percentage       = 100
    }
  }
}

# --------------------------------------------------------------------------
# agent (supervision agent)
# --------------------------------------------------------------------------

resource "azurerm_container_app" "agent" {
  name                         = "ca-${local.prefix}-agent"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  tags                          = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.agent.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.agent.id
  }

  template {
    # Single replica: the polling scheduler holds no distributed lock yet
    # (specs.md §9 roadmap item "verrou distribué"), so scaling out would
    # double-collect and double-publish metrics.
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "agent"
      image  = "${azurerm_container_registry.this.login_server}/agent:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "MCP_GOLD_URL"
        value = "https://${var.mcp_gold_onprem_host}:${var.mcp_gold_port}/mcp"
      }
      env {
        name  = "MCP_RELEX_GENERIX_URL"
        value = "https://${azurerm_container_app.mcp_relex_generix.ingress[0].fqdn}/mcp"
      }
      env {
        name  = "POLL_INTERVAL_SECONDS"
        value = "60"
      }

      liveness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000
      }
    }
  }

  ingress {
    external_enabled = false
    target_port       = 8000
    transport          = "http"

    traffic_weight {
      latest_revision = true
      percentage       = 100
    }
  }
}

# --------------------------------------------------------------------------
# prometheus
# --------------------------------------------------------------------------

resource "azurerm_container_app" "prometheus" {
  name                         = "ca-${local.prefix}-prometheus"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  tags                          = local.tags

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "prometheus"
      image  = "docker.io/prom/prometheus:latest"
      cpu    = 0.5
      memory = "1Gi"

      # Rétention explicite : par défaut Prometheus ne garde que 15 jours.
      # prometheus_retention_days détermine combien de temps en arrière on
      # peut "revoir les indicateurs d'une certaine période" dans Grafana.
      args = [
        "--config.file=/etc/prometheus/prometheus.yml",
        "--storage.tsdb.path=/prometheus",
        "--storage.tsdb.retention.time=${var.prometheus_retention_days}d",
        "--web.console.libraries=/usr/share/prometheus/console_libraries",
        "--web.console.templates=/usr/share/prometheus/consoles",
      ]

      volume_mounts {
        name = "config"
        path = "/etc/prometheus"
      }
      volume_mounts {
        name = "data"
        path = "/prometheus"
      }
    }

    volume {
      name         = "config"
      storage_name = azurerm_container_app_environment_storage.prometheus_config.name
      storage_type = "AzureFile"
    }
    volume {
      name         = "data"
      storage_name = azurerm_container_app_environment_storage.prometheus_data.name
      storage_type = "AzureFile"
    }
  }

  ingress {
    external_enabled = false
    target_port       = 9090
    transport          = "http"

    traffic_weight {
      latest_revision = true
      percentage       = 100
    }
  }
}

# --------------------------------------------------------------------------
# grafana — the only externally-reachable app
# --------------------------------------------------------------------------

resource "azurerm_container_app" "grafana" {
  name                         = "ca-${local.prefix}-grafana"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  tags                          = local.tags

  depends_on = [time_sleep.wait_for_kv_rbac] # let the Key Vault Secrets User grant propagate first

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.grafana.id]
  }

  # TEMPORARY: see the matching comment on mcp_relex_generix above and
  # azure-deployment.md for the full diagnostic trail — literal values as an
  # unblock (grafana-admin-password / teams-webhook-url are still
  # placeholders, see variables.tf defaults) until the Key Vault secret
  # reference timeout is understood. Revert to key_vault_secret_id + identity
  # once real credentials are in play.
  secret {
    name  = "grafana-admin-password"
    value = var.grafana_admin_password
  }
  secret {
    name  = "teams-webhook-url"
    value = var.teams_webhook_url
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "grafana"
      image  = "docker.io/grafana/grafana:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "GF_SECURITY_ADMIN_PASSWORD"
        secret_name = "grafana-admin-password"
      }
      env {
        name  = "GF_AUTH_ANONYMOUS_ENABLED"
        value = "false"
      }
      env {
        name  = "GF_UNIFIED_ALERTING_ENABLED"
        value = "true"
      }
      env {
        # Consommé par monitoring/grafana/provisioning/alerting/contactpoints.yaml
        # via $__env{TEAMS_WEBHOOK_URL} (specs.md §9.1 "Grafana ... route les alertes").
        name        = "TEAMS_WEBHOOK_URL"
        secret_name = "teams-webhook-url"
      }

      volume_mounts {
        name = "provisioning"
        path = "/etc/grafana/provisioning"
      }
    }

    volume {
      name         = "provisioning"
      storage_name = azurerm_container_app_environment_storage.grafana_provisioning.name
      storage_type = "AzureFile"
    }
  }

  ingress {
    external_enabled = true
    target_port       = 3000
    transport          = "http"

    traffic_weight {
      latest_revision = true
      percentage       = 100
    }

    dynamic "ip_security_restriction" {
      for_each = { for idx, cidr in var.allowed_ip_ranges_for_grafana : idx => cidr }
      content {
        name             = "allow-${ip_security_restriction.key}"
        action           = "Allow"
        ip_address_range = ip_security_restriction.value
      }
    }
  }
}

# NOTE: Entra ID (Easy Auth) on the Grafana ingress is not yet expressible
# as a stable azurerm resource at the time of writing. Wire it up after
# `terraform apply` with:
#   az containerapp auth microsoft update \
#     --name <grafana app name> --resource-group <rg name> \
#     --client-id <app-registration-id> --client-secret <secret> \
#     --tenant-id <tenant-id>
# See specs.md §9.1 ("Grafana ... authentification Entra ID").
