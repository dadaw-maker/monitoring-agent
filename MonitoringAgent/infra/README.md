# Infra — Azure Container Apps + couche de sécurité

Provisionne tout ce qui, dans `specs.md §9`, vit dans **Azure** : l'environnement Container Apps, `mcp-relex-generix`, l'agent, Prometheus, Grafana, plus la couche sécurité (réseau, Key Vault, identités, VPN, journalisation). **`mcp_gold` n'est pas provisionné ici** : il doit être déployé on-premises dans le datacenter LabelVie (voir `../README.md`).

## Couche de sécurité incluse

| Domaine | Mise en œuvre |
|---|---|
| Réseau | VNet dédié, subnet ACA délégué, NSG par défaut-deny avec allow-list explicite (RELEX/Generix 443, on-prem GOLD sur port unique, Azure Cloud), table de routage forçant le trafic on-prem via la gateway VPN |
| VPN | Site-à-site IPsec/IKEv2 vers le datacenter LabelVie (`azurerm_virtual_network_gateway` + `azurerm_local_network_gateway`) |
| Identités | Une identité managée par service Azure, aucune identité partagée |
| Autorisations | RBAC least-privilege : `AcrPull` et `Key Vault Secrets User` uniquement, jamais `Contributor`/`Owner` |
| Secrets | Key Vault RBAC-only, purge protection, soft-delete 90j, réseau public désactivé, private endpoint |
| Registre | ACR Premium, admin désactivé, private endpoint, token scope-map dédié pour le pull on-prem de `mcp_gold` |
| Stockage | Compte de stockage (config Prometheus/Grafana) sans accès public, private endpoint |
| Traçabilité | Log Analytics + diagnostic settings sur Key Vault et ACR (§9.4 "qu'a lu la supervision, et quand ?") |
| Ingress | Tout est interne sauf Grafana (seul point d'entrée externe, restreignable par CIDR) |
| Défense en profondeur (optionnel) | Microsoft Defender for Cloud (Key Vault, ACR) et NSG flow logs, activables via variables |

## Utilisation

```bash
cd infra
terraform init
cp terraform.tfvars.example terraform.tfvars   # puis éditer
terraform plan
terraform apply
```

Après le premier `apply` :
1. Construire et pousser les 3 images (`mcp-relex-generix`, `agent`, `mcp-gold`) vers l'ACR créé (`terraform output container_registry_login_server`).
2. Remplacer les secrets `changeme` par les vraies valeurs directement dans le Key Vault (`terraform output key_vault_name`) — Terraform ignore ensuite les changements de valeur (`lifecycle.ignore_changes`), donc pas de conflit au prochain `apply`.
3. Basculer `GOLD_MODE` / `RELEX_MODE` / `GENERIX_MODE` sur `live` une fois les credentials réels en place (variable Terraform, ou directement le secret Key Vault `*-mode` puis redéploiement du revision Container App).
3bis. Renseigner le secret Key Vault `teams-webhook-url` (URL d'un webhook entrant créé sur un canal Teams) pour activer l'alerte — voir `../monitoring/grafana/provisioning/alerting/`. Laissé à `changeme`, Grafana tourne mais n'envoie rien.
4. Déployer `mcp_gold` on-premises avec le token ACR scope-map créé (`terraform output mcp_gold_acr_pull_token_name`).
5. Finaliser l'authentification Entra ID sur Grafana (commande `az containerapp auth microsoft update`, voir commentaire en fin de `container_apps.tf`).

## Notes

- `deploy_vpn_gateway = false` permet d'itérer sans provisionner la VPN Gateway (ressource coûteuse, ~plusieurs dizaines d'euros/mois), utile en tout début de projet — remettre à `true` avant la mise en pilote réelle.
- Un backend Terraform distant (`azurerm` storage account) est recommandé dès que plusieurs personnes appliquent ce code — voir le bloc commenté dans `providers.tf`.
- Schéma `azurerm_container_app` en évolution rapide : lancer `terraform validate` après `terraform init` pour rattraper d'éventuels changements d'arguments selon la version du provider.
