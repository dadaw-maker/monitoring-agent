# CI/CD — pipeline de déploiement GitHub Actions → Azure

Trois workflows, dans `.github/workflows/` (à la racine du dépôt, pas dans `MonitoringAgent/` — GitHub n'y cherche que là) :

| Fichier | Déclencheur | Ce qu'il fait |
|---|---|---|
| `tests.yml` | PR ou push sur `main` touchant `MonitoringAgent/**` | Compile-check + `pytest` (20 tests). Pas de credentials Azure requis. |
| `terraform-plan.yml` | PR touchant `MonitoringAgent/infra/**` | `terraform plan` en lecture seule, commenté sur la PR. N'applique jamais rien. |
| `deploy-azure.yml` | Push sur `main`, ou déclenchement manuel | Build + push des 3 images vers l'ACR, puis `terraform apply`. |

Authentification par **OIDC (identité fédérée)** : aucun mot de passe ni secret Azure long-lived n'est stocké dans GitHub — un jeton GitHub à courte durée de vie est échangé contre un jeton Azure au moment de l'exécution.

---

## Étape A — Bootstrapper le backend Terraform (état distant)

Terraform a besoin d'un endroit pour stocker son état, séparé de l'infra qu'il gère (un backend ne peut pas se créer lui-même). À faire une seule fois, avec `az` en local ou en Cloud Shell :

```bash
az group create -n rg-ordermgmt-tfstate -l francecentral
az storage account create -n stordermgmttfstate -g rg-ordermgmt-tfstate -l francecentral --sku Standard_LRS
az storage container create -n tfstate --account-name stordermgmttfstate
```

(Adapter les noms si `stordermgmttfstate` est déjà pris ailleurs — les noms de comptes de stockage Azure sont globalement uniques.)

## Étape B — Créer l'App Registration (identité fédérée GitHub)

```bash
APP_ID=$(az ad app create --display-name "github-ordermgmt-deploy" --query appId -o tsv)
az ad sp create --id "$APP_ID"
SP_OBJECT_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "AZURE_CLIENT_ID=$APP_ID"
echo "AZURE_CLIENT_OBJECT_ID=$SP_OBJECT_ID"
echo "AZURE_TENANT_ID=$TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
```

Deux identifiants de fédération sont nécessaires — un par forme de jeton que GitHub émet selon le workflow (voir tableau ci-dessus) :

```bash
OWNER_REPO="dadaw-maker/monitoring-agent"   # à adapter si le dépôt est renommé à nouveau

az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-azure-production-environment",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:'"$OWNER_REPO"':environment:azure-production",
  "audiences": ["api://AzureADTokenExchange"]
}'

az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-pull-requests",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:'"$OWNER_REPO"':pull_request",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

Droits (à ajuster selon votre politique — voir note ci-dessous) :

```bash
az role assignment create --assignee "$APP_ID" --role "Contributor" --scope "/subscriptions/$SUBSCRIPTION_ID"
az role assignment create --assignee "$APP_ID" --role "User Access Administrator" --scope "/subscriptions/$SUBSCRIPTION_ID"
```

> `User Access Administrator` est nécessaire parce que Terraform crée lui-même des `azurerm_role_assignment` (identités managées → Key Vault, ACR...). Pour un scope plus étroit qu'une souscription entière : créer le resource group `rg-ordermgmt-<env>` manuellement, importer-le dans le state Terraform (`terraform import azurerm_resource_group.this <id>`), et scoper les deux rôles ci-dessus sur ce resource group au lieu de la souscription.

## Étape C — Configurer GitHub : variables et secrets du dépôt

**Settings → Secrets and variables → Actions → Variables** (non sensibles) :

| Nom | Valeur |
|---|---|
| `AZURE_CLIENT_ID` | sortie de l'étape B |
| `AZURE_CLIENT_OBJECT_ID` | sortie de l'étape B (`SP_OBJECT_ID`) |
| `AZURE_TENANT_ID` | sortie de l'étape B |
| `AZURE_SUBSCRIPTION_ID` | sortie de l'étape B |
| `TF_BACKEND_RESOURCE_GROUP` | `rg-ordermgmt-tfstate` |
| `TF_BACKEND_STORAGE_ACCOUNT` | `stordermgmttfstate` |
| `TF_BACKEND_CONTAINER` | `tfstate` |
| `TF_BACKEND_KEY` | `ordermgmt.tfstate` |
| `ACR_LOGIN_SERVER` | voir Étape E (n'existe qu'après le tout premier apply) |

**Settings → Secrets and variables → Actions → Secrets** (sensibles — correspondent aux variables Terraform du même nom en minuscules, voir `infra/variables.tf`) :

`TF_ONPREM_ADDRESS_SPACE`, `TF_ONPREM_VPN_GATEWAY_IP`, `TF_MCP_GOLD_ONPREM_HOST`, `TF_VPN_SHARED_KEY`, `TF_GRAFANA_ADMIN_PASSWORD`, `TF_TEAMS_WEBHOOK_URL`, `TF_ORACLE_DSN`, `TF_ORACLE_USER`, `TF_ORACLE_PASSWORD`, `TF_RELEX_CLIENT_ID`, `TF_RELEX_CLIENT_SECRET`, `TF_RELEX_API_KEY`, `TF_GENERIX_API_KEY`.

Tous ont un défaut (`changeme` ou `stub`) dans `infra/variables.tf` — inutile de renseigner tout de suite ceux que vous n'utilisez pas encore (ex. tant que `GOLD_MODE=stub`, `TF_ORACLE_*` peuvent rester absents).

## Étape D — Créer l'environnement GitHub `azure-production`

**Settings → Environments → New environment** → nommer `azure-production`. Ajouter des **required reviewers** pour transformer le déploiement automatique (push sur `main`) en déploiement avec approbation manuelle — recommandé avant de connecter de vraies sources RELEX/GOLD/Generix.

## Étape E — Premier bootstrap (une fois, en partie manuel)

`deploy-azure.yml` a besoin d'`ACR_LOGIN_SERVER` pour savoir où pousser les images — qui n'existe qu'après un premier `terraform apply`. Poule et œuf classique : la toute première fois se fait donc à la main (voir `DEPLOYMENT.md` étapes 2-4), puis on bascule sur le pipeline pour tous les déploiements suivants :

```bash
cd MonitoringAgent/infra
terraform init -backend-config=backend.hcl   # cf. backend.hcl.example
terraform apply -target=azurerm_resource_group.this -target=azurerm_container_registry.this -target=azurerm_key_vault.this

# noter le nom de l'ACR pour la variable GitHub ACR_LOGIN_SERVER
terraform output container_registry_login_server

# construire/pousser les 3 images une première fois (voir DEPLOYMENT.md étape 3)
# puis :
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
| `terraform init` échoue sur le backend | Vérifier les 4 variables `TF_BACKEND_*` et que le compte de stockage/conteneur de l'Étape A existent |
| `az acr login` échoue (403) | Le rôle `AcrPush` n'a pas été accordé — vérifier que `AZURE_CLIENT_OBJECT_ID` est bien renseigné et qu'un `terraform apply` a tourné après (résout `azurerm_role_assignment.acr_push_github_actions` dans `infra/identity.tf`) |
| Le job `terraform-apply` ne se lance jamais | L'environnement `azure-production` attend une approbation (Étape D) — normal si des reviewers sont configurés |
