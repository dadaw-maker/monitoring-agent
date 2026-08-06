# CI/CD — pipeline de déploiement GitHub Actions → Azure

Trois workflows, dans `.github/workflows/` (à la racine du dépôt, pas dans `MonitoringAgent/` — GitHub n'y cherche que là) :

| Fichier | Déclencheur | Ce qu'il fait |
|---|---|---|
| `tests.yml` | PR ou push sur `main` touchant `MonitoringAgent/**` | Compile-check + `pytest` (20 tests). Pas de credentials Azure requis. |
| `terraform-plan.yml` | PR touchant `MonitoringAgent/infra/**` | `terraform plan` en lecture seule, commenté sur la PR. N'applique jamais rien. |
| `deploy-azure.yml` | Push sur `main`, ou déclenchement manuel | Build + push des 3 images vers l'ACR, puis `terraform apply`. |

Authentification par **OIDC (identité fédérée)** : aucun mot de passe ni secret Azure long-lived n'est stocké dans GitHub — un jeton GitHub à courte durée de vie est échangé contre un jeton Azure au moment de l'exécution.

Ce guide part d'un **resource group déjà existant** — `lbv-rg-monitoring-agent-ordermgnt` (West Europe) — plutôt que d'en faire créer un nouveau par ces commandes. Tout (état Terraform, identité CI, infra applicative) y vit, ce qui évite d'avoir besoin de droits de création de resource group au niveau de l'abonnement : tout ce qui suit ne demande que le rôle **Contributor** (+ **User Access Administrator**) sur ce seul resource group.

---

## Étape A — Bootstrapper le backend Terraform (état distant)

Terraform a besoin d'un endroit pour stocker son état, séparé de l'infra qu'il gère. À faire une seule fois, avec `az` en local ou en Cloud Shell :

```bash
RG="lbv-rg-monitoring-agent-ordermgnt"

az storage account create -n stordermgmttfstate -g "$RG" -l westeurope --sku Standard_LRS
az storage container create -n tfstate --account-name stordermgmttfstate
```

(Adapter `stordermgmttfstate` s'il est déjà pris ailleurs — les noms de comptes de stockage Azure sont globalement uniques. Pas besoin de `az group create` : on réutilise `$RG`.)

## Étape B — Créer l'identité fédérée GitHub

Une *User-Assigned Managed Identity* est une ressource Azure comme une autre : elle se crée avec un rôle **Contributor** classique sur un resource group, **sans avoir besoin d'un rôle d'administrateur d'annuaire Entra ID** (contrairement à un App Registration, qui nécessite le rôle *Application Developer* ou davantage côté Entra ID). Elle supporte l'identité fédérée OIDC exactement de la même façon.

```bash
RG="lbv-rg-monitoring-agent-ordermgnt"

az identity create --name github-ordermgmt-deploy --resource-group "$RG"

CLIENT_ID=$(az identity show --name github-ordermgmt-deploy --resource-group "$RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show --name github-ordermgmt-deploy --resource-group "$RG" --query principalId -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "AZURE_CLIENT_ID=$CLIENT_ID"
echo "AZURE_CLIENT_OBJECT_ID=$PRINCIPAL_ID"
echo "AZURE_TENANT_ID=$TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"

OWNER_REPO="dadaw-maker/monitoring-agent"   # à adapter si le dépôt est renommé à nouveau

az identity federated-credential create \
  --name github-azure-production-environment \
  --identity-name github-ordermgmt-deploy \
  --resource-group "$RG" \
  --issuer "https://token.actions.githubusercontent.com" \
  --subject "repo:${OWNER_REPO}:environment:azure-production" \
  --audiences "api://AzureADTokenExchange"

az identity federated-credential create \
  --name github-pull-requests \
  --identity-name github-ordermgmt-deploy \
  --resource-group "$RG" \
  --issuer "https://token.actions.githubusercontent.com" \
  --subject "repo:${OWNER_REPO}:pull_request" \
  --audiences "api://AzureADTokenExchange"

RG_SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG"
az role assignment create --assignee "$PRINCIPAL_ID" --role "Contributor" --scope "$RG_SCOPE"
az role assignment create --assignee "$PRINCIPAL_ID" --role "User Access Administrator" --scope "$RG_SCOPE"
```

Les rôles sont scopés au resource group (`$RG_SCOPE`), pas à toute la souscription — cohérent avec le fait que vos propres droits sont probablement, eux aussi, scopés à ce resource group plutôt qu'à la souscription entière.

> `User Access Administrator` est nécessaire parce que Terraform crée lui-même des `azurerm_role_assignment` (identités managées de l'agent/mcp-relex-generix/grafana → Key Vault, ACR...) — toutes scopées à des ressources qui vivent dans `$RG`, donc le rôle scopé au resource group suffit.
>
> Si même `az identity create` échoue par manque de droits : demandez à la personne qui gère l'abonnement/le resource group de lancer exactement ce bloc, puis de vous communiquer les 4 valeurs `AZURE_*` affichées par les `echo` — c'est tout ce dont vous avez besoin ensuite, aucun accès Azure permanent n'est requis pour la suite.

## Étape C — Configurer GitHub : variables et secrets du dépôt

**Settings → Secrets and variables → Actions → Variables** (non sensibles) :

| Nom | Valeur |
|---|---|
| `AZURE_CLIENT_ID` | sortie de l'étape B (`$CLIENT_ID`) |
| `AZURE_CLIENT_OBJECT_ID` | sortie de l'étape B (`$PRINCIPAL_ID`) |
| `AZURE_TENANT_ID` | sortie de l'étape B |
| `AZURE_SUBSCRIPTION_ID` | sortie de l'étape B |
| `TF_BACKEND_RESOURCE_GROUP` | `lbv-rg-monitoring-agent-ordermgnt` |
| `TF_BACKEND_STORAGE_ACCOUNT` | `stordermgmttfstate` |
| `TF_BACKEND_CONTAINER` | `tfstate` |
| `TF_BACKEND_KEY` | `ordermgmt.tfstate` |
| `ACR_LOGIN_SERVER` | voir Étape F (n'existe qu'après le tout premier apply) |

**Settings → Secrets and variables → Actions → Secrets** (sensibles — correspondent aux variables Terraform du même nom en minuscules, voir `infra/variables.tf`) :

`TF_ONPREM_ADDRESS_SPACE`, `TF_ONPREM_VPN_GATEWAY_IP`, `TF_MCP_GOLD_ONPREM_HOST`, `TF_VPN_SHARED_KEY`, `TF_GRAFANA_ADMIN_PASSWORD`, `TF_TEAMS_WEBHOOK_URL`, `TF_ORACLE_DSN`, `TF_ORACLE_USER`, `TF_ORACLE_PASSWORD`, `TF_RELEX_CLIENT_ID`, `TF_RELEX_CLIENT_SECRET`, `TF_RELEX_API_KEY`, `TF_GENERIX_API_KEY`.

Tous ont un défaut (`changeme` ou `stub`) dans `infra/variables.tf` — inutile de renseigner tout de suite ceux que vous n'utilisez pas encore (ex. tant que `GOLD_MODE=stub`, `TF_ORACLE_*` peuvent rester absents).

## Étape D — Créer l'environnement GitHub `azure-production`

**Settings → Environments → New environment** → nommer `azure-production`. Ajouter des **required reviewers** pour transformer le déploiement automatique (push sur `main`) en déploiement avec approbation manuelle — recommandé avant de connecter de vraies sources RELEX/GOLD/Generix.

## Étape E — Adopter le resource group existant dans `terraform.tfvars`

```bash
# MonitoringAgent/infra/terraform.tfvars
project              = "ordermgmt"
environment           = "dev"
location              = "westeurope"
resource_group_name   = "lbv-rg-monitoring-agent-ordermgnt"
```

(déjà pré-rempli ainsi dans `terraform.tfvars.example` — copier vers `terraform.tfvars` et compléter le reste : `onprem_address_space`, `onprem_vpn_gateway_public_ip`, `mcp_gold_onprem_host`, `vpn_shared_key`.)

## Étape F — Premier bootstrap (une fois, en partie manuel)

`deploy-azure.yml` a besoin d'`ACR_LOGIN_SERVER` pour savoir où pousser les images — qui n'existe qu'après un premier `terraform apply`. Poule et œuf classique : la toute première fois se fait donc à la main, puis on bascule sur le pipeline pour tous les déploiements suivants.

Comme `lbv-rg-monitoring-agent-ordermgnt` existe déjà en dehors de Terraform, il faut d'abord le lui faire "adopter" (`terraform import`) avant tout `apply` — sinon Terraform tente de le *créer* et échoue avec "resource already exists" :

```bash
cd MonitoringAgent/infra
terraform init -backend-config=backend.hcl   # cf. backend.hcl.example

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
terraform import azurerm_resource_group.this \
  "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/lbv-rg-monitoring-agent-ordermgnt"

terraform apply -target=azurerm_resource_group.this -target=azurerm_container_registry.this -target=azurerm_key_vault.this

# noter le nom de l'ACR pour la variable GitHub ACR_LOGIN_SERVER
terraform output container_registry_login_server

# construire/pousser les 3 images une première fois (voir DEPLOYMENT.md étape 3)
# puis, une fois AZURE_CLIENT_OBJECT_ID renseigné côté GitHub (Étape C) pour
# que le rôle AcrPush du pipeline soit bien créé :
terraform apply
```

Une fois `ACR_LOGIN_SERVER` renseigné dans les variables GitHub (Étape C), tous les déploiements suivants passent par `deploy-azure.yml`.

---

## Comment ça marche ensuite

1. Une PR modifiant `MonitoringAgent/**` déclenche `tests.yml` ; si elle touche `infra/**`, `terraform-plan.yml` commente le plan sur la PR.
2. Un merge sur `main` déclenche `deploy-azure.yml` : build + push des 3 images (tag = SHA du commit + `latest`), puis `terraform apply` qui redéploie les Container Apps sur ce nouveau tag.
3. Si l'environnement `azure-production` a des reviewers requis (Étape D), le workflow s'arrête avant `terraform-apply` en attendant une approbation dans l'onglet Actions.
4. Déclenchement manuel possible à tout moment : Actions → "Deploy MonitoringAgent to Azure" → "Run workflow" (case "apply" à cocher pour appliquer, décochée pour un simple plan).

## Dépannage

| Symptôme | Piste |
|---|---|
| `azure/login` échoue avec une erreur AADSTS70021 (no matching federated identity) | Le `subject` du federated credential ne correspond pas exactement à ce que GitHub envoie — vérifier que le job utilise bien `environment: azure-production` (ou aucun environment, pour le cas `pull_request`) |
| `terraform apply` échoue avec "A resource with the ID ... already exists" sur le resource group | L'import de l'Étape F n'a pas été fait — relancer `terraform import azurerm_resource_group.this ...` |
| `terraform init` échoue sur le backend | Vérifier les 4 variables `TF_BACKEND_*` et que le compte de stockage/conteneur de l'Étape A existent |
| `az acr login` échoue (403) | Le rôle `AcrPush` n'a pas été accordé — vérifier que `AZURE_CLIENT_OBJECT_ID` est bien renseigné et qu'un `terraform apply` a tourné après (résout `azurerm_role_assignment.acr_push_github_actions` dans `infra/identity.tf`) |
| Le job `terraform-apply` ne se lance jamais | L'environnement `azure-production` attend une approbation (Étape D) — normal si des reviewers sont configurés |
