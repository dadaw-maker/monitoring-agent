# Journal de déploiement Azure — LabelVie

Suivi concret du bootstrap CI/CD pour **ce** déploiement (valeurs réelles, pas génériques — le guide générique reste [`CI-CD.md`](./CI-CD.md)). Tout se fait depuis le **Cloud Shell Azure** (portal.azure.com → icône Cloud Shell).

## Valeurs de ce déploiement

| Élément | Valeur |
|---|---|
| Resource group (existant, adopté par Terraform) | `lbv-rg-monitoring-agent-ordermgnt` |
| Région | West Europe |
| Compte de stockage — backend Terraform | `stordermgmttfstate` |
| Container — backend Terraform | `tfstate` |
| Identité managée CI/CD | `github-ordermgmt-deploy` |
| Dépôt GitHub | `dadaw-maker/monitoring-agent` |
| GitHub Organization ID (numérique) | `270965870` |
| GitHub Repository ID (numérique) | `1191809919` |
| Environnement GitHub | `azure-production` |

## État d'avancement

- [x] **Étape A** — Compte de stockage `stordermgmttfstate` + container `tfstate` créés (via le Portail, Primary service = *Azure Blob Storage or Azure Data Lake Storage Gen 2*, Standard, LRS)
- [x] **Étape B** — Identité managée `github-ordermgmt-deploy` créée, avec :
  - Federated credential `github-azure-production-environment` (Entity type: Environment, valeur `azure-production`)
  - Federated credential `github-pull-requests` (Entity type: Pull request)
  - Rôle **Contributor** sur `lbv-rg-monitoring-agent-ordermgnt`
  - Rôle **User Access Administrator** sur `lbv-rg-monitoring-agent-ordermgnt` (a nécessité que l'admin élargisse la condition de délégation sur son propre rôle, ou fasse l'attribution lui-même — bloqué un moment sur ce point)
- [x] **Étape C** — Variables GitHub créées (`Settings → Secrets and variables → Actions → Variables`) : `AZURE_CLIENT_ID`, `AZURE_CLIENT_OBJECT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `TF_BACKEND_RESOURCE_GROUP`, `TF_BACKEND_STORAGE_ACCOUNT`, `TF_BACKEND_CONTAINER`, `TF_BACKEND_KEY`
- [x] **Étape D** — Environnement GitHub `azure-production` créé
- [ ] **Étape F** — Premier bootstrap Terraform + images (en cours, voir ci-dessous)
- [ ] Variable GitHub `ACR_LOGIN_SERVER` (viendra après le premier `apply` partiel)
- [ ] `terraform apply` complet
- [ ] Vérification : dashboard Grafana accessible, données stub visibles

---

## Étape F — Premier bootstrap (Cloud Shell)

### Bloc 1 — cloner le dépôt et initialiser Terraform

```bash
git clone https://github.com/dadaw-maker/monitoring-agent.git
cd monitoring-agent
git checkout claude/agent-azure-container-order-management-qf4arn
cd MonitoringAgent/infra

cat > backend.hcl <<'EOF'
resource_group_name  = "lbv-rg-monitoring-agent-ordermgnt"
storage_account_name = "stordermgmttfstate"
container_name        = "tfstate"
key                    = "ordermgmt.tfstate"
EOF

terraform init -backend-config=backend.hcl
```

### Bloc 2 — fichier de variables (mode stub, VPN Gateway désactivé pour ce premier déploiement)

⚠️ **À faire avant le Bloc 3** : `terraform import` charge toute la configuration et a donc besoin de connaître les variables obligatoires (`mcp_gold_onprem_host`, `onprem_address_space`, `onprem_vpn_gateway_public_ip`, `vpn_shared_key`) — sans ce fichier, il les demande une par une en interactif.

Le vrai GOLD n'est pas encore connecté à ce stade (`GOLD_MODE=stub`) — inutile de provisionner le VPN Gateway (le plus long et le plus coûteux à créer) tout de suite. Les valeurs `onprem_*`/`vpn_shared_key` ci-dessous sont des **placeholders**, à remplacer le jour où GOLD est réellement raccordé et `deploy_vpn_gateway` repassé à `true`.

```bash
cat > terraform.tfvars <<'EOF'
project              = "ordermgmt"
environment           = "dev"
location              = "westeurope"
resource_group_name   = "lbv-rg-monitoring-agent-ordermgnt"

deploy_vpn_gateway            = false
onprem_address_space          = "10.100.0.0/16"
onprem_vpn_gateway_public_ip  = "203.0.113.10"
mcp_gold_onprem_host          = "mcp-gold.labelvie.internal"
vpn_shared_key                 = "changeme"

gold_mode     = "stub"
relex_mode    = "stub"
generix_mode  = "stub"
EOF
```

### Bloc 3 — adopter le resource group existant dans le state Terraform

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
terraform import azurerm_resource_group.this "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/lbv-rg-monitoring-agent-ordermgnt"
```

Doit se terminer par *"Import successful!"*.

### Bloc 4 — premier apply partiel (juste de quoi pousser des images)

```bash
terraform apply -target=azurerm_resource_group.this -target=azurerm_container_registry.this -target=azurerm_key_vault.this
```

Puis noter le nom de l'ACR :

```bash
terraform output container_registry_login_server
```

→ à coller dans la variable GitHub `ACR_LOGIN_SERVER` (`Settings → Secrets and variables → Actions → Variables`).

### Bloc 5 — construire et pousser les 3 images une première fois

⚠️ Cloud Shell ne peut pas faire tourner de démon Docker (`docker build`/`docker push` échouent avec *"This command requires running the docker daemon, which is not supported in Azure Cloud Shell"*). On utilise **`az acr build`** à la place : le build se fait directement sur les serveurs de l'ACR, sans Docker local, et pousse l'image dans le même mouvement.

```bash
cd ../..   # revenir à MonitoringAgent/ depuis infra/
ACR=$(terraform -chdir=infra output -raw container_registry_login_server | cut -d. -f1)

az acr build --registry "$ACR" --image agent:latest --file services/agent/Dockerfile .
az acr build --registry "$ACR" --image mcp-gold:latest --file services/mcp_gold/Dockerfile .
az acr build --registry "$ACR" --image mcp-relex-generix:latest --file services/mcp_relex_generix/Dockerfile .
```

### Bloc 6 — apply complet

```bash
cd infra
terraform apply
```

Crée le réseau, le Key Vault, les identités, et les 4 Container Apps (agent, mcp-relex-generix, prometheus, grafana). `mcp-gold` n'est volontairement pas ici — il est prévu pour tourner on-premises, mais pour ce premier test on peut le laisser non déployé et l'agent tournera avec `mcp-gold` injoignable (indicateurs `COL-*`/`TRA-*`/`WMS-*` à `UNKNOWN`, le reste fonctionne).

À la fin :

```bash
terraform output grafana_url
```

→ ouvrir cette URL, se connecter (admin / secret Key Vault `grafana-admin-password`).

---

## Une fois le bootstrap fait

Tous les déploiements suivants passent par le pipeline GitHub Actions (`deploy-azure.yml`) — plus besoin de repasser par le Cloud Shell, sauf changement de credentials ou de secrets.
