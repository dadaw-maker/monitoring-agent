output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "container_registry_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "key_vault_name" {
  value = azurerm_key_vault.this.name
}

output "grafana_url" {
  value = "https://${azurerm_container_app.grafana.ingress[0].fqdn}"
}

output "agent_internal_fqdn" {
  description = "Reachable only from inside the Container Apps environment / peered VNets"
  value       = azurerm_container_app.agent.ingress[0].fqdn
}

output "mcp_relex_generix_internal_fqdn" {
  value = azurerm_container_app.mcp_relex_generix.ingress[0].fqdn
}

output "vpn_gateway_public_ip" {
  value = var.deploy_vpn_gateway ? azurerm_public_ip.vpn[0].ip_address : null
}

output "mcp_gold_acr_pull_token_name" {
  description = "Use `az acr token credential generate` with this token name to get on-prem pull credentials for mcp_gold"
  value       = azurerm_container_registry_token.mcp_gold_pull.name
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.this.id
}
