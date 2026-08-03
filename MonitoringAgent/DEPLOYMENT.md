# Guide de déploiement — MonitoringAgent

Ce document explique, étape par étape, comment déployer tout le projet : d'abord en local (mode stub, sans aucun accès aux vrais systèmes), puis sur Azure, puis en connectant les vraies sources (GOLD, RELEX, Generix). Il complète `README.md` (vue d'ensemble) et `infra/README.md` (détails Terraform).

---

## Arborescence complète du projet

```
MonitoringAgent/
├── specs.md                          # Spécifications fonctionnelles : les 34 indicateurs unitaires,
│                                      # les 6 indicateurs chapeau + l'indicateur de tête, l'architecture cible
├── README.md                         # Vue d'ensemble du projet et utilisation locale
├── DEPLOYMENT.md                     # Ce document
├── .env.example                      # Modèle de fichier de variables d'environnement pour le local
├── .gitignore                        # Exclut caches Python, .env, état Terraform du dépôt
├── docker-compose.yml                # Lance les 5 services (2 MCP + agent + Prometheus + Grafana) en local
│
├── libs/ordermgmt_common/            # Code Python partagé par les 3 services
│   ├── __init__.py
│   ├── models.py                     # Définit à quoi ressemble un "résultat d'indicateur" (valeur, statut OK/WARNING/CRITICAL...)
│   └── connector_mode.py             # Lit la variable d'environnement stub/live (GOLD_MODE, RELEX_MODE, GENERIX_MODE)
│
├── services/
│   │
│   ├── mcp_gold/                     # Serveur MCP qui lit GOLD (Oracle, sur site LabelVie)
│   │   ├── Dockerfile                # Recette pour construire l'image de ce serveur
│   │   ├── requirements.txt          # Dépendances Python de ce serveur
│   │   └── app/
│   │       ├── config.py             # Paramètres (port, credentials Oracle...) lus depuis l'environnement
│   │       ├── connectors.py         # Logique de lecture des données : version "stub" (fictive) active,
│   │       │                         # version "réelle" (Oracle) présente en commentaire, prête à activer
│   │       └── server.py             # Démarre le serveur MCP et déclare les outils consultables par l'agent
│   │
│   ├── mcp_relex_generix/            # Serveur MCP qui lit RELEX et le WMS Generix/Infolog (tous deux en SaaS)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── config.py
│   │       ├── connectors.py         # Idem : stub actif, connexions réelles RELEX/Generix en commentaire
│   │       └── server.py
│   │
│   └── agent/                        # L'agent de supervision : le cerveau du projet
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── config.py             # Paramètres (URLs des serveurs MCP, seuils d'alerte...)
│           ├── mcp_clients.py        # Sait appeler un outil sur un serveur MCP et récupérer le résultat
│           ├── indicators_unitaires.py  # Calcule les 34 indicateurs unitaires (COL-1 à E2E-5) à partir des données brutes
│           ├── indicators_chapeau.py    # Combine les unitaires pour produire les 6 indicateurs chapeau + l'indicateur de tête
│           ├── scheduler.py          # Boucle qui tourne toutes les 60s : interroge les 2 serveurs MCP, calcule, publie
│           ├── metrics_exporter.py   # Transforme les résultats en métriques au format Prometheus
│           └── main.py               # Serveur web de l'agent : /health, /metrics, /indicators
│
├── monitoring/                       # Configuration prête à l'emploi pour Prometheus et Grafana
│   ├── prometheus/prometheus.yml     # Dit à Prometheus où aller chercher les métriques (l'agent)
│   └── grafana/provisioning/
│       ├── datasources/prometheus.yml   # Dit à Grafana où trouver Prometheus
│       └── dashboards/
│           ├── dashboards.yml            # Dit à Grafana où trouver les fichiers de tableaux de bord
│           └── json/order-management.json  # Le tableau de bord lui-même (statuts, indicateurs)
│
├── infra/                            # Tout le code Terraform pour créer les ressources Azure
│   ├── providers.tf                  # Quelle version de Terraform et du plugin Azure utiliser
│   ├── variables.tf                  # La liste de tous les réglages personnalisables (région, credentials, IP du VPN...)
│   ├── terraform.tfvars.example      # Exemple de fichier à copier/remplir avec vos propres valeurs
│   ├── main.tf                       # Crée le groupe de ressources Azure (le "dossier" qui contiendra tout)
│   ├── network.tf                    # Crée le réseau : VNet, sous-réseaux, pare-feu (NSG), VPN vers le datacenter LabelVie
│   ├── acr.tf                        # Crée le registre d'images Docker (Azure Container Registry)
│   ├── keyvault.tf                   # Crée le coffre-fort à secrets (mots de passe, clés API)
│   ├── identity.tf                   # Crée une "identité" par service Azure, pour qu'il puisse s'authentifier sans mot de passe
│   ├── storage.tf                    # Crée le stockage de fichiers qui contient la config Prometheus/Grafana
│   ├── container_apps.tf             # Crée les 4 applications Azure (agent, mcp-relex-generix, Prometheus, Grafana)
│   ├── monitoring.tf                 # Crée le suivi des journaux (Log Analytics) et les options de sécurité avancées
│   ├── outputs.tf                    # Affiche les informations utiles après le déploiement (URL Grafana, nom de l'ACR...)
│   └── README.md                     # Détails techniques Terraform (déjà présent, complète ce guide)
│
└── tests/                            # Tests automatiques qui vérifient que le calcul des indicateurs est correct
    ├── conftest.py                   # Utilitaire pour que les tests puissent importer les 3 services
    ├── requirements.txt
    ├── test_indicators_unitaires.py
    ├── test_indicators_chapeau.py
    └── test_connectors_stub.py
```

---

## Vue d'ensemble des étapes

| # | Étape | Ce que ça fait |
|---|---|---|
| 1 | Tester en local | Vérifier que tout fonctionne, avec des données fictives (stub), sans toucher à Azure ni aux vrais systèmes |
| 2 | Provisionner Azure (partie 1) | Créer le réseau, le coffre-fort, le registre d'images |
| 3 | Construire et pousser les images | Mettre les 3 programmes (agent, mcp-gold, mcp-relex-generix) dans le registre Azure |
| 4 | Provisionner Azure (partie 2) | Créer les applications qui font réellement tourner le projet dans Azure |
| 5 | Déployer `mcp_gold` sur site | Installer le serveur qui lit Oracle GOLD dans le datacenter LabelVie |
| 6 | Vérifier que tout tourne en mode stub | Confirmer que le tableau de bord Grafana s'affiche, avec des données fictives |
| 7 | Basculer une source en réel | Décommenter le connecteur, renseigner les vrais identifiants, redéployer |
| 8 | Finaliser la sécurité de Grafana | Restreindre l'accès au tableau de bord aux comptes LabelVie (Entra ID) |

---

## Étape 1 — Tester en local

**Ce que ça fait** : lance les 5 services sur votre machine avec Docker, en mode stub (données fictives). Permet de valider que le pipeline complet fonctionne (collecte → calcul des indicateurs → tableau de bord) avant de toucher à Azure.

```bash
cd MonitoringAgent
cp .env.example .env
docker compose up --build
```

Vérifications :
- http://localhost:8000/health → `{"status":"ok", ...}`
- http://localhost:8000/indicators → les 34 indicateurs + 7 chapeaux, en JSON
- http://localhost:9090 → Prometheus, avec les métriques `order_mgmt_*`
- http://localhost:3000 → Grafana (admin / valeur de `GRAFANA_ADMIN_PASSWORD` dans `.env`), tableau de bord "Order Management" déjà provisionné

Si cette étape fonctionne, tout le code métier (calcul des indicateurs) est validé — le reste du guide ne fait que le déployer ailleurs.

---

## Étape 2 — Provisionner Azure (partie 1 : réseau, coffre-fort, registre)

**Ce que ça fait** : crée les fondations Azure — réseau sécurisé, VPN vers le datacenter LabelVie, coffre-fort à secrets, registre d'images. On s'arrête avant de créer les applications, car elles ont besoin que les images Docker existent déjà dans le registre.

```bash
cd infra
terraform init
cp terraform.tfvars.example terraform.tfvars
# éditer terraform.tfvars : renseigner au minimum onprem_address_space,
# onprem_vpn_gateway_public_ip, mcp_gold_onprem_host, vpn_shared_key
terraform apply \
  -target=azurerm_resource_group.this \
  -target=azurerm_container_registry.this \
  -target=azurerm_key_vault.this
```

À la fin, notez le nom du registre :
```bash
terraform output container_registry_login_server
```

*(Si vous préférez ne pas faire l'apply en deux temps, vous pouvez lancer `terraform apply` complet directement — Terraform créera d'abord toutes les ressources indépendantes, puis échouera uniquement sur les 3 `azurerm_container_app` faute d'image ; il suffit de relancer `terraform apply` après l'étape 3.)*

---

## Étape 3 — Construire et pousser les images Docker

**Ce que ça fait** : transforme le code Python de chaque service en image Docker, et l'envoie dans le registre Azure créé à l'étape 2, pour qu'Azure puisse ensuite la faire tourner.

```bash
ACR=$(terraform -chdir=infra output -raw container_registry_login_server)
az acr login --name "${ACR%%.*}"

cd ..  # revenir à MonitoringAgent/
docker build -f services/agent/Dockerfile              -t "$ACR/agent:latest"             .
docker build -f services/mcp_gold/Dockerfile            -t "$ACR/mcp-gold:latest"          .
docker build -f services/mcp_relex_generix/Dockerfile   -t "$ACR/mcp-relex-generix:latest" .

docker push "$ACR/agent:latest"
docker push "$ACR/mcp-gold:latest"
docker push "$ACR/mcp-relex-generix:latest"
```

> `mcp-gold` sera poussé ici pour être ensuite récupéré par le serveur **on-premises** (étape 5) — il ne tourne jamais dans Azure Container Apps (voir architecture, `specs.md §9`).

---

## Étape 4 — Provisionner Azure (partie 2 : les applications)

**Ce que ça fait** : crée les 4 applications Azure Container Apps (agent, mcp-relex-generix, Prometheus, Grafana), maintenant que leurs images existent dans le registre.

```bash
cd infra
terraform apply
```

Récupérez l'URL publique de Grafana :
```bash
terraform output grafana_url
```

---

## Étape 5 — Déployer `mcp_gold` sur site (datacenter LabelVie)

**Ce que ça fait** : installe, dans le datacenter LabelVie (pas dans Azure), le serveur qui lit directement la base Oracle GOLD. C'est le seul composant qui ne vit pas dans Azure, car GOLD est on-premises.

```bash
# Récupérer le nom du token de pull dédié (créé par acr.tf, sans les droits admin du registre)
terraform output mcp_gold_acr_pull_token_name

# Générer les identifiants de connexion associés à ce token
az acr token credential generate \
  --name <nom-du-token> \
  --registry <nom-de-l-acr>

# Sur le serveur on-premises, se connecter au registre puis récupérer l'image
docker login <acr-login-server> -u <token-name> -p <mot-de-passe-généré>
docker pull <acr-login-server>/mcp-gold:latest
docker run -d --name mcp-gold -p 8001:8001 \
  -e GOLD_MODE=stub \
  <acr-login-server>/mcp-gold:latest
```

À ce stade, `mcp_gold` tourne encore en mode **stub** (données fictives) — c'est volontaire, voir étape 7 pour le passage en réel.

---

## Étape 6 — Vérifier que tout tourne en mode stub

**Ce que ça fait** : confirme que l'agent Azure arrive bien à joindre `mcp_gold` on-premises à travers le VPN, et que le tableau de bord Grafana affiche des données (fictives à ce stade).

1. Ouvrir `terraform output grafana_url` dans un navigateur, se connecter (admin / secret Key Vault `grafana-admin-password`)
2. Vérifier que le tableau de bord "Order Management" affiche les 7 statuts (chapeau + tête) et les 34 indicateurs
3. Si rien ne s'affiche : vérifier les logs de l'agent (`az containerapp logs show --name <ca-agent>`) — la cause la plus fréquente est un problème de connectivité VPN entre Azure et `mcp_gold`

Tant que cette étape n'est pas verte avec des données stub, ne passez pas à l'étape 7 : un problème réseau ou de configuration est plus facile à diagnostiquer sans mélanger ça à un problème de credentials réels.

---

## Étape 7 — Basculer une source de stub à réel

**Ce que ça fait** : remplace les données fictives d'un système par les vraies données, une source à la fois. Recommandé dans cet ordre : GOLD, puis RELEX, puis Generix (l'ordre du flux métier, du plus en amont au plus en aval).

Pour chaque système (exemple avec GOLD) :

1. **Décommenter le connecteur réel** dans `services/mcp_gold/app/connectors.py` : le bloc `LiveGoldConnector` et la ligne `return LiveGoldConnector()` dans `build_gold_connector()`. Ces lignes sont volontairement commentées par défaut — c'est un garde-fou : impossible de partir en production sur un vrai système par accident.
2. **Confirmer les détails techniques manquants** avec l'équipe concernée (noms de vues Oracle pour GOLD, endpoints exacts pour RELEX, interface REST/SOAP pour Generix — voir les `TODO` dans le code et `specs.md §7`), et ajuster les requêtes si besoin.
3. **Renseigner les vrais identifiants** directement dans le Key Vault (jamais dans le code ni dans Terraform) :
   ```bash
   az keyvault secret set --vault-name <nom-du-kv> --name oracle-dsn      --value "<vraie-valeur>"
   az keyvault secret set --vault-name <nom-du-kv> --name oracle-user     --value "<vraie-valeur>"
   az keyvault secret set --vault-name <nom-du-kv> --name oracle-password --value "<vraie-valeur>"
   az keyvault secret set --vault-name <nom-du-kv> --name gold-mode       --value "live"
   ```
4. **Reconstruire et repousser l'image** modifiée (étape 3, pour ce service uniquement).
5. **Redéployer** : pour `mcp_gold` (on-prem), `docker pull` + `docker restart` avec `-e GOLD_MODE=live` ; pour les services Azure, `az containerapp update --name <ca-...> --image <acr>/<service>:latest` (ou relancer `terraform apply` si l'image porte un tag différent de `latest`).
6. **Vérifier** sur Grafana que les indicateurs concernés passent de `source_mode=stub` à `source_mode=live` (visible aussi sur `/indicators`), et que les valeurs ont du sens.

Répéter pour RELEX (`RELEX_MODE`, fichier `services/mcp_relex_generix/app/connectors.py`, classe `LiveRelexConnector`) puis Generix (`GENERIX_MODE`, même fichier, classe `LiveGenerixConnector`).

---

## Étape 8 — Finaliser la sécurité de Grafana

**Ce que ça fait** : restreint l'accès au tableau de bord aux comptes Microsoft Entra ID de LabelVie, au lieu d'un simple mot de passe partagé.

```bash
az containerapp auth microsoft update \
  --name <ca-...-grafana> --resource-group <rg-...> \
  --client-id <id-app-registration> --client-secret <secret> \
  --tenant-id <tenant-id>
```

Voir le commentaire en fin de `infra/container_apps.tf` pour le contexte complet.

---

## En cas de problème

| Symptôme | Piste |
|---|---|
| `terraform apply` échoue sur les `azurerm_container_app` | Les images ne sont pas encore dans l'ACR — refaire l'étape 3 puis relancer `terraform apply` |
| Grafana affiche des trous / pas de données | Vérifier `/health` et `/indicators` sur l'agent ; vérifier les logs du conteneur `agent` |
| L'agent ne joint pas `mcp_gold` | Vérifier le VPN (`terraform output vpn_gateway_public_ip`), la route on-prem, le port ouvert dans le NSG (`infra/network.tf`) |
| `GOLD_MODE=live` mais toujours des données stub | Le bloc `LiveGoldConnector` n'a probablement pas été décommenté (étape 7, point 1) — l'agent lèvera une erreur explicite dans les logs si c'est le cas |
| Tests locaux en échec | `pip install -r services/agent/requirements.txt -r tests/requirements.txt` puis `PYTHONPATH=tests pytest tests/ -v` depuis `MonitoringAgent/` |
