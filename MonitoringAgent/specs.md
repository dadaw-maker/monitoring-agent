# MonitoringAgent — Agent de Supervision Order Management

## 1. Vision du produit

MonitoringAgent est un agent IA de supervision du **flux de gestion des commandes** (Order Management), déployé sur **Azure Container Apps**. Il surveille en continu plusieurs systèmes hétérogènes (ERP Oracle, Relex, Generix), calcule des indicateurs de suivi, expose un dashboard temps réel et déclenche des alertes en cas d'anomalie.

Contrairement à un simple script de monitoring, MonitoringAgent s'appuie sur le **Claude Agent SDK** : au-delà de la collecte automatique et de l'alerting, il permet d'interroger l'état des commandes en langage naturel et de diagnostiquer une anomalie (ex. *"Pourquoi les commandes du site Lyon sont bloquées depuis ce matin ?"*).

---

## 2. Systèmes sources et intégrations

| Système | Rôle | Mode d'accès |
|---|---|---|
| **ERP Oracle** | Référentiel commandes, statuts, données financières | Accès direct base Oracle via un **serveur MCP Oracle** (lecture seule) |
| **Relex** | Prévision de la demande / réapprovisionnement | **API REST** |
| **Generix** | Échanges EDI / Supply Chain (flux fournisseurs, transporteurs) | **SOAP / EDI** |

L'agent Claude consomme l'accès Oracle comme un **outil MCP** (le serveur MCP Oracle expose des requêtes SQL contrôlées et restreintes en lecture), tandis que Relex et Generix sont intégrés via des connecteurs applicatifs classiques (REST / SOAP) qui alimentent le même pipeline de métriques.

---

## 3. Indicateurs de suivi (KPIs)

### 3.1 Statuts & cycle de vie des commandes
- Répartition des commandes par statut (créée, validée, en préparation, expédiée, livrée, annulée, en erreur)
- Commandes "stagnantes" : bloquées dans un même statut au-delà d'un seuil de temps
- Taux de commandes annulées / modifiées après validation

### 3.2 Délais & SLA
- Temps de traitement moyen par étape (validation → préparation → expédition → livraison)
- Taux de dépassement de SLA (par étape et global)
- Retards de livraison / traitement vs délai contractuel

### 3.3 Erreurs & anomalies
- Taux d'échec par cause (paiement, stock, intégration EDI, rejet Oracle)
- Commandes en erreur technique (échec de synchronisation ERP ↔ Relex ↔ Generix)
- Détection de doublons

### 3.4 Volume & tendances
- Nombre de commandes par heure / jour / site
- Détection de pics ou creux anormaux (vs moyenne mobile / période comparable)
- Comparaison de volumes entre systèmes (cohérence Oracle vs Relex vs Generix)

### 3.5 Table de synthèse

| Indicateur | Source | Fréquence de calcul | Seuil d'alerte (par défaut) |
|---|---|---|---|
| % commandes en dépassement SLA | Oracle | 5 min | > 5 % |
| Commandes stagnantes > 4h dans un statut | Oracle | 5 min | > 10 commandes |
| Taux d'échec technique (intégration) | Oracle + Relex + Generix | 5 min | > 2 % |
| Écart de volume Oracle vs Relex vs Generix | Multi-source | 15 min | écart > 5 % |
| Variation de volume horaire vs moyenne mobile 7j | Oracle | 15 min | ± 30 % |
| Latence flux EDI Generix | Generix | 5 min | > 30 min sans accusé de réception |

Les seuils sont configurables (fichier de config / variables d'environnement) et ajustables par site ou par type de commande.

---

## 4. Architecture technique

```
┌─────────────────────────────────────────────────────────────┐
│                     Azure Container Apps                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              MonitoringAgent (FastAPI)                 │  │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐ │  │
│  │  │  Claude    │  │ Scheduler  │  │  API REST         │ │  │
│  │  │  Agent SDK │  │ (APSched.) │  │  /health /ask     │ │  │
│  │  │  (diagnostic│ │  polling   │  │  /metrics         │ │  │
│  │  │  conversat.)│ │  périodique│  │                    │ │  │
│  │  └─────┬──────┘  └─────┬──────┘  └──────────────────┘ │  │
│  │        │               │                               │  │
│  │  ┌─────▼───────────────▼─────────────────────────────┐ │  │
│  │  │              Connecteurs                           │ │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │ │  │
│  │  │  │ Oracle   │  │ Relex    │  │ Generix          │ │ │  │
│  │  │  │ (MCP,    │  │ (REST)   │  │ (SOAP/EDI)       │ │ │  │
│  │  │  │ lecture  │  │          │  │                  │ │ │  │
│  │  │  │ seule)   │  │          │  │                  │ │ │  │
│  │  │  └──────────┘  └──────────┘  └──────────────────┘ │ │  │
│  │  └─────────────────────────────────────────────────────┘ │
│  │  ┌─────────────────────────────────────────────────────┐ │
│  │  │        Notifieurs (Email · Microsoft Teams)          │ │
│  │  └─────────────────────────────────────────────────────┘ │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────┬────────────────────────────────┘
                            │ /metrics (Prometheus format)
                  ┌─────────▼─────────┐        ┌───────────────┐
                  │   Prometheus       │───────▶│   Grafana     │
                  │ (scrape périodique)│        │  (dashboards) │
                  └────────────────────┘        └───────────────┘
```

### 4.1 Stack technique

| Couche | Technologie |
|---|---|
| Langage / framework | Python 3.12 + FastAPI |
| Agent IA | Claude Agent SDK (Anthropic) |
| Accès Oracle | Serveur MCP Oracle (lecture seule) |
| Client REST (Relex) | `httpx` |
| Client SOAP/EDI (Generix) | `zeep` (SOAP) + parseur EDI dédié |
| Ordonnancement | `APScheduler` (polling périodique) |
| Métriques | `prometheus-client` (endpoint `/metrics`) |
| Dashboard | Grafana (scrape Prometheus) |
| Alerting | SMTP / Microsoft Graph (Email), Webhook entrant Teams |
| Conteneurisation | Docker |
| Déploiement | Azure Container Apps + Azure Container Registry |
| Secrets | Azure Key Vault (credentials Oracle, Relex, Generix, Teams, SMTP) |
| Observabilité infra | Azure Log Analytics / Application Insights |
| IaC | Bicep (ou Terraform) |
| CI/CD | GitHub Actions → build image → push ACR → déploiement Container Apps |

### 4.2 Déploiement Azure Container Apps

- **Container App principale** : expose l'API FastAPI (`/health`, `/metrics`, `/ask`) et exécute le scheduler de polling en tâche de fond.
- **Azure Container Apps Jobs** (optionnel, phase 2) : exécution de collectes lourdes (rapprochement multi-source Oracle/Relex/Generix) en jobs planifiés plutôt qu'en polling in-process.
- **Scaling** : règles KEDA basées sur la charge HTTP (dashboard/API) ; le worker de polling reste à réplique unique pour éviter les doubles collectes (verrou distribué si scale > 1).
- **Secrets** : injectés via Azure Key Vault + références de secrets Container Apps (aucune credential en clair dans l'image ou le repo).
- **Réseau** : accès sortant restreint aux endpoints Oracle (VPN/Private Link si ERP on-prem), Relex et Generix ; environnement Container Apps rattaché à un VNet si nécessaire pour joindre l'ERP.

---

## 5. Fonctionnalités principales

### 5.1 Collecte automatique
- Polling périodique des 3 sources (fréquences différenciées par indicateur, cf. §3.5)
- Normalisation des données en un modèle de commande unifié (`UnifiedOrder`)
- Calcul des indicateurs et exposition au format Prometheus

### 5.2 Alerting
- Évaluation des seuils après chaque cycle de collecte
- Envoi Email + notification Microsoft Teams (webhook) en cas de dépassement
- Anti-spam : regroupement des alertes similaires, cooldown configurable

### 5.3 Dashboard Grafana
- Vue globale : volumes, statuts, SLA par système et par site
- Vue par système source (Oracle / Relex / Generix) avec statut de synchronisation
- Historique des alertes déclenchées

### 5.4 Agent conversationnel (diagnostic)
- Endpoint `/ask` : question en langage naturel sur l'état des commandes
- L'agent (Claude Agent SDK) interroge l'outil MCP Oracle et les connecteurs Relex/Generix pour construire une réponse contextualisée
- Cas d'usage : diagnostic de blocage, explication d'un pic d'erreurs, résumé quotidien

---

## 6. Sécurité et conformité

- Accès Oracle strictement **lecture seule** via MCP (pas d'écriture possible depuis l'agent)
- Credentials stockés exclusivement dans Azure Key Vault
- HTTPS obligatoire sur l'API exposée
- Logs sans données personnelles/sensibles (masquage des données client dans les logs)
- Traçabilité des alertes envoyées (audit trail)

---

## 7. Structure du répertoire

```
MonitoringAgent/
├── specs.md
├── src/
│   ├── agent/            # Intégration Claude Agent SDK, logique de diagnostic
│   ├── connectors/
│   │   ├── oracle_mcp.py
│   │   ├── relex_rest.py
│   │   └── generix_soap_edi.py
│   ├── metrics/           # Calcul des indicateurs + exporteur Prometheus
│   ├── alerting/
│   │   ├── email_notifier.py
│   │   └── teams_notifier.py
│   ├── api/                # Routes FastAPI (/health, /metrics, /ask)
│   ├── scheduler/          # Polling périodique (APScheduler)
│   └── config/
├── infra/                  # Bicep/Terraform (Container Apps, ACR, Key Vault, Log Analytics)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml  # app + prometheus + grafana (environnement local)
├── tests/
└── .github/workflows/       # CI/CD build + push ACR + déploiement Container Apps
```

---

## 8. Roadmap

### Phase 1 — MVP (collecte + alerting de base)
- [ ] Connecteur Oracle via MCP (lecture seule) — indicateurs statuts & SLA
- [ ] Connecteur Relex (REST) — indicateurs volume
- [ ] Connecteur Generix (SOAP/EDI) — indicateurs erreurs/latence EDI
- [ ] Exposition `/metrics` (Prometheus) + endpoint `/health`
- [ ] Alerting Email + Teams sur seuils par défaut
- [ ] Dockerfile + déploiement manuel sur Azure Container Apps

### Phase 2 — Dashboard & fiabilisation
- [ ] Dashboards Grafana (global, par système, historique alertes)
- [ ] IaC Bicep/Terraform complet (ACA, ACR, Key Vault, Log Analytics)
- [ ] CI/CD GitHub Actions (build/push/déploiement automatisé)
- [ ] Rapprochement multi-source (cohérence Oracle/Relex/Generix) en Azure Container Apps Job

### Phase 3 — Agent conversationnel
- [ ] Endpoint `/ask` avec Claude Agent SDK
- [ ] Diagnostic assisté (corrélation multi-source sur incident)
- [ ] Résumé quotidien automatique envoyé par email/Teams

### Phase 4 — Industrialisation
- [ ] Seuils d'alerte configurables par site/type de commande
- [ ] Scaling KEDA + verrou distribué pour le scheduler
- [ ] Tests de charge et audit sécurité

---

## 9. Indicateurs de performance de l'agent lui-même

| Indicateur | Cible |
|---|---|
| Latence de détection d'une anomalie | < 5 min après occurrence |
| Disponibilité de l'agent | 99,5 % |
| Taux de faux positifs sur les alertes | < 10 % |
| Fraîcheur des données (âge max des métriques exposées) | < 15 min |

---

*Document de spécifications — MonitoringAgent — Version 1.0 — Août 2026*
