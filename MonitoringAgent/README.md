# MonitoringAgent

Supervision du processus Order Management LabelVie (O4HQ → GOLD → RELEX → GOLD → WMS Infolog/Generix). Voir [`specs.md`](./specs.md) pour la grille complète des indicateurs et l'architecture cible, et [`DEPLOYMENT.md`](./DEPLOYMENT.md) pour la marche à suivre complète, étape par étape, du test local jusqu'au passage en production.

## Structure

```
MonitoringAgent/
├── specs.md
├── libs/ordermgmt_common/        # modèles Pydantic partagés (IndicatorResult, ChapeauResult)
├── services/
│   ├── mcp_gold/                 # serveur MCP GOLD (Oracle, on-prem) — lecture seule
│   ├── mcp_relex_generix/        # serveur MCP RELEX (OTel) + Generix/WMS (REST)
│   └── agent/                    # agent de supervision : polling, calcul indicateurs, /metrics
├── monitoring/                    # config Prometheus + provisioning Grafana (local & Azure)
├── infra/                          # Terraform Azure (Container Apps, sécurité, réseau)
├── docker-compose.yml              # stack complète en local
└── tests/
```

## Lancer en local

```bash
cp .env.example .env
docker compose up --build
```

- Agent : http://localhost:8000/health, /metrics, /indicators
- Prometheus : http://localhost:9090
- Grafana : http://localhost:3000 (admin / voir `GRAFANA_ADMIN_PASSWORD`) — dashboard "Order Management" reproduisant la maquette de `specs.md §8` (3 sections : L'essentiel du jour / Où en est la chaîne / Ce qui demande une décision), plus une section technique repliée avec les codes d'indicateurs bruts pour l'exploitation
- MCP GOLD : http://localhost:8001 (protocole MCP, pas un site web classique)
- MCP RELEX/Generix : http://localhost:8002

### Historique des indicateurs

Prometheus persiste son historique dans un volume (Docker nommé en local, Azure File share en production — `infra/storage.tf`), avec une rétention configurable (`PROMETHEUS_RETENTION_DAYS` en local, `prometheus_retention_days` en Terraform ; 400 jours par défaut en Azure). L'historique survit donc à un redémarrage/redéploiement, et peut être revu sur n'importe quelle période via le sélecteur de plage temporelle de Grafana ou une requête PromQL avec `[Xd]`.

### Alerte Teams

Grafana route les alertes vers Teams (specs.md §9.1) via `monitoring/grafana/provisioning/alerting/` (point de contact, politique de notification, règles sur l'indicateur de tête, les indicateurs chapeau et les échecs de collecte de l'agent). Renseigner `TEAMS_WEBHOOK_URL` dans `.env` (local) ou le secret Key Vault `teams-webhook-url` (Azure) — voir DEPLOYMENT.md.

Par défaut, tout tourne en mode **stub** (`GOLD_MODE=RELEX_MODE=GENERIX_MODE=stub`) : les trois connecteurs renvoient des données fictives mais réalistes, ce qui permet de faire tourner tout le pipeline — MCP → agent → indicateurs → Prometheus → Grafana — sans aucun accès aux systèmes réels.

## Passer un connecteur en mode réel ("live")

Chaque connecteur (GOLD/Oracle, RELEX, Generix) a une implémentation stub et une implémentation "live" derrière la même interface (voir `services/*/app/connectors.py`). Le choix se fait uniquement via une variable d'environnement, lue au démarrage :

| Variable | Valeurs | Service |
|---|---|---|
| `GOLD_MODE` | `stub` \| `live` | mcp_gold |
| `RELEX_MODE` | `stub` \| `live` | mcp_relex_generix |
| `GENERIX_MODE` | `stub` \| `live` | mcp_relex_generix |

Pour brancher une source réelle : renseigner les credentials correspondants (`ORACLE_*`, `RELEX_*`, `GENERIX_*` — voir `.env.example`), passer la variable de mode à `live`, redéployer. **Aucun changement de code n'est nécessaire.** En production, ces credentials viennent d'Azure Key Vault (`infra/keyvault.tf`), jamais de variables en clair.

⚠️ Les connecteurs `live` sont des squelettes fonctionnels (connexion, auth, requêtes) mais certains noms de vues Oracle, endpoints RELEX/Generix exacts restent à confirmer avec les équipes GOLD / RELEX (WZM) / l'intégrateur IDL — voir `specs.md §7` et les commentaires `TODO` dans le code.

## Déploiement cible (Azure)

- `mcp_gold` : à déployer **on-premises** dans le datacenter LabelVie (au contact d'Oracle), relié à Azure par le VPN site-à-site — n'est **pas** provisionné par le Terraform de ce dépôt.
- `mcp_relex_generix`, `agent`, `prometheus`, `grafana` : Azure Container Apps, provisionnés par `infra/` (voir `infra/README.md`).

## Tests

```bash
cd MonitoringAgent
pip install -r services/agent/requirements.txt -r tests/requirements.txt
PYTHONPATH=libs:services/agent pytest tests/
```
