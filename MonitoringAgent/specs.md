# MonitoringAgent — Spécifications
## Supervision du processus Order Management — LabelVie

> Ce document reprend et structure la *Note d'Architecture — Métriques de supervision Order Management* (LabelVie / Pôle TECH, V1.0, 28/07/2026) comme spécification du projet MonitoringAgent. Il remplace la première version générique de ce fichier : les indicateurs, seuils et l'architecture ci-dessous sont ceux validés dans la note source.

---

## 1. Contexte

Le processus Order Management couvre la chaîne : **Serveur Central O4HQ → GOLD → RELEX → GOLD → WMS**, de la collecte des ventes magasin jusqu'à l'envoi de l'ordre de préparation à l'entrepôt.

**Contrainte structurante** : RELEX et le WMS sont en **SaaS**, GOLD est **on-premises**, et seul RELEX expose nativement une API OpenTelemetry — ce qui détermine les métriques réellement disponibles par système.

## 2. Objectifs

Construire une première grille d'indicateurs — **1 indicateur de tête**, **6 indicateurs chapeau** pour le pilotage, **38 indicateurs unitaires** pour le diagnostic — afin de **mesurer l'état de fonctionnement réel du processus et anticiper les incidents**, au lieu de constater les pannes. Si l'approche est validée, elle sera étendue à d'autres processus métier.

## 3. Méthode — deux niveaux de lecture

- **Indicateurs chapeau (§5)** : répondent chacun à une question métier et portent l'alerte ; ils combinent plusieurs indicateurs unitaires.
- **Indicateurs unitaires (§6)** : mesurent une étape précise et servent au diagnostic.

Deux niveaux de mesure, applicables à chaque indicateur unitaire :

| Niveau | Nature | Usage |
|---|---|---|
| Niveau 1 | État instantané (disponibilité, statut d'exécution) | Alerte |
| Niveau 2 | Agrégat sur une période (volumes, taux, délais) | Suivi et engagements de service |

Chaque indicateur unitaire porte : un **type** (technique ou fonctionnel), un **niveau** (1 ou 2), une **priorité**, un **seuil d'alerte** et une **complexité d'implémentation**.

---

## 4. Cartographie des flux inter-systèmes

| # | Flux | Nature technique | Description | DAGs Airflow | Remarque / niveau de confiance |
|---|---|---|---|---|---|
| ① | O4HQ → GOLD | Batch nocturne, hors Airflow | Remontée des ventes consolidées des magasins vers GOLD (extraction CSV PostgreSQL o4hq_prod → SFTP → staging Oracle → intégration par procédure stockée). PostgreSQL et Oracle ne communiquent qu'via ce fichier CSV. | Aucun DAG identifié | **Angle mort prioritaire** : aucune alerte en cas d'échec, alors qu'il conditionne le flux ②. À instrumenter avec l'équipe GOLD. |
| ② | GOLD → RELEX | Extraction batch | Historique de ventes et stock transmis à RELEX pour le calcul de réassort. | 28 DAGs. Cœur ventes/stock (7) : `relex-write-spool-sales-transactions-dag`, `relex-write-spool-sales-transactions-7days-dag`, `relex-write-spool-dc-sales-transactions-dag`, `relex-write-spool-balances-dag`, `relex-write-spool-balances-extraction-dag`, `relex-write-spool-batch-balances-transactions-dag`, `relex-write-spool-inventory-transactions-dag` ; 21 référentiel + variantes | Supervision niveau 1 sur les 7 DAGs ventes/stock (**CAL-8**) ; les 21 référentiel restants agrégés en niveau 2 (**CAL-9**). |
| ③ | RELEX → GOLD | API asynchrone (non confirmée) | Flux « Order Proposals » + fallback « Reserve Order Proposals ». | `relex-read-order-proposals-dag`, `relex-read-order-proposals-reserve-dag`, `relex-read-projections-forecasts-dag`, `relex-infolog-stock-dlc-dag` | ⚠ Nature non confirmée — relecture du code des 4 DAGs nécessaire avant instrumentation. Statut technique des 4 DAGs suivi indépendamment de cette confirmation (**TRA-6**). |
| ④ | GOLD → WMS | API / import fichier | Commande de réassort transmise au WMS, cut-off différencié par enseigne. | `wms-schedule-dag` (orchestrateur, 5 passages/jour : 01:00, 03:00, 05:00, 06:00, 07:00) + 9 DAGs interfaces m10→m91 | Cut-off par enseigne à confirmer dans le code. Statut de l'orchestrateur suivi par **WMS-2**, des 9 interfaces par **WMS-9**. |
| ⑤ | RELEX ↔ WMS | Flux direct SaaS↔SaaS, hors GOLD | Identifié mais **non qualifié ni instrumenté** — priorité de supervision. | `wms-relex-write-spool-m91-dag` transite en réalité par GOLD/SFTP — ce n'est pas ce flux | À qualifier avant toute supervision. |
| ⑥ | WMS → Magasin | Flux physique | Expédition entrepôt → magasin. | Sans objet | Hors périmètre de supervision applicative. |
| ⑦ | WMS → GOLD | Retour (à confirmer) | Confirmation d'expédition / mise à jour de stock. | `wms-write-spool-m41-dag`, `m51-dag`, `m8001-dag`, `m91-dag` | Mêmes 4 DAGs que le flux ④ — couverts techniquement par **WMS-9** en attendant confirmation du sens de lecture ; inclusion au pilote à trancher. |

> **Périmètre Airflow (v1.1)** — l'inventaire complet du parc LabelVie compte 153 DAGs (`Inventaire_DAGs_LabelVie_153.xlsx`). 43 sont rattachés aux flux ①–⑤ et ⑦ ci-dessus et entrent dans le périmètre de cette note. Les 110 restants servent d'autres domaines (HELPDESK, ATACADAO/ATC, ASSORTIMENT, PROMO, AGIRH, AGRESSO, fidélité, e-commerce…) sans lien avec le flux de commandes et restent hors périmètre.

---

## 5. Indicateur de tête et indicateurs chapeau

| Question métier | Indicateur chapeau (combinaison d'unitaires) | Unitaires de diagnostic | Impact si défaillance |
|---|---|---|---|
| **Le processus a-t-il bien tourné cette nuit ?** *(indicateur de tête)* | Part des magasins ayant reçu, avant le cut-off de leur enseigne, une commande de réassort exploitable = **COL-2 et CAL-4 et WMS-6 et WMS-8** | Les 6 indicateurs chapeau ci-dessous | Forte — réassort du jour compromis |
| Les ventes de la nuit sont-elles toutes remontées ? | Collecte nocturne conforme = **COL-1 et COL-2** | COL-3, COL-4, COL-5, COL-6 (§6.1) | Forte — sans ventes, aucun besoin calculable |
| Le calcul a-t-il produit une proposition pour chaque magasin ? | Calcul complet = **CAL-1 et CAL-4 et CAL-6 et CAL-8** | CAL-2, CAL-3, CAL-5, CAL-7, CAL-9 (§6.2) | Forte — aucune commande générée pour les magasins non couverts |
| Les propositions sont-elles devenues des commandes dans GOLD ? | Transmission intègre = **TRA-1 et TRA-4 et TRA-6** | TRA-2, TRA-3, TRA-5 (§6.3) | Forte — propositions perdues silencieusement |
| Les commandes partiront-elles à l'entrepôt à temps ? | Départ dans les délais = **WMS-6 et WMS-1 et WMS-8 et WMS-9** | WMS-2, WMS-3, WMS-4, WMS-5, WMS-7 (§6.4) | Forte — livraison décalée à J+1 |
| Un flux hors GOLD peut-il invalider ce constat ? | Couverture du flux direct = **DIR-1** | DIR-2, DIR-3 (§6.5) | Moyenne — non quantifiable tant que non qualifié |
| La chaîne se dégrade-t-elle dans le temps ? | Tenue de la chaîne = **E2E-1 et E2E-4 et E2E-2** | E2E-3, E2E-5, CAL-5 (§6.6) | Faible à court terme, moyenne en cumulé |

---

## 6. Grille des indicateurs unitaires

### 6.1 Collecte des données amont (O4HQ → GOLD)

| Indicateur | Type | Niv. | Priorité | Description | Mesure | Seuil d'alerte | Complexité |
|---|---|---|---|---|---|---|---|
| **COL-1** — Exécution du batch nocturne O4HQ → GOLD | Technique | 1 | Haute | Le batch s'est-il exécuté et terminé dans la fenêtre nocturne ? Aucun DAG ne le supervise (flux ①). | Statut/heure de fin sur un point de contrôle à définir avec GOLD | Aucune fin de traitement à l'heure limite convenue | Élevée — aucun point de contrôle existant |
| **COL-2** — Taux de succès de remontée O4HQ | Fonctionnel | 1 | Haute | Part des magasins ayant remonté leurs ventes à l'heure attendue. | Magasins remontés / magasins attendus, à l'heure de référence | < 100 % des magasins remontés | Moyenne |
| **COL-3** — Latence de mise à jour du stock GOLD | Technique | 1 | Moyenne | Délai entre le mouvement de stock et son écriture dans GOLD. | Écart horodatage mouvement / écriture | À calibrer après observation | Moyenne |
| **COL-4** — Anomalies et rejets à la collecte | Technique | 2 | Moyenne | Formats invalides, doublons, données corrompues à l'ingestion. | Nb lignes rejetées / lignes reçues, par type d'erreur | À calibrer (référence à établir) | Faible |
| **COL-5** — Complétude des données pour le calcul RELEX | Fonctionnel | 2 | Haute | Magasins manquants ou historique trop court pour un réassort fiable. | Contrôle de complétude avant calcul RELEX | ≥ 1 magasin manquant, ou historique insuffisant | Moyenne |
| **COL-6** — Cohérence stock GOLD vs stock physique | Fonctionnel | 2 | Basse | Écart stock système / stock réel, fausse le calcul du besoin. | Écart relatif GOLD vs stock compté, par site | Écart > tolérance métier | Élevée — dépend du plan d'inventaire |

### 6.2 Calcul du besoin de réassort (RELEX)

| Indicateur | Type | Niv. | Priorité | Description | Mesure | Seuil d'alerte | Complexité |
|---|---|---|---|---|---|---|---|
| **CAL-1** — Disponibilité du service RELEX | Technique | 1 | Haute | Service up / dégradé / down. | API OTel RELEX | Statut ≠ « up » | Faible — API OTel disponible |
| **CAL-2** — Durée du calcul de réassort | Technique | 1 | Moyenne | Temps d'exécution du calcul. | Durée du span, médiane | À calibrer sur durée nominale | Faible |
| **CAL-3** — Taux d'erreur ou de timeout du calcul | Technique | 1 | Haute | Échecs techniques ou dépassements de délai. | Part d'exécutions en erreur/timeout (traces OTel) | Toute exécution en erreur/timeout | Faible |
| **CAL-4** — Propositions générées vs attendues | Fonctionnel | 2 | Haute | Détecte un calcul partiel. | Propositions reçues / couples magasin-article attendus | Écart > tolérance métier | Moyenne |
| **CAL-5** — Durée moyenne du calcul (période) | Technique | 2 | Moyenne | Dérive progressive de performance. | Moyenne glissante vs référence initiale | Dérive vs référence (seuil à calibrer) | Faible |
| **CAL-6** — Taux d'activation du flux de secours | Fonctionnel | 2 | Haute | Résilience du PCA RELEX. | Nb/durée des recours au flux de secours / cycles | Toute activation | Faible |
| **CAL-7** — Taux de propositions en anomalie fonctionnelle | Fonctionnel | 2 | Moyenne | Quantité nulle, DLC incohérente, contrainte de stock non respectée. | Part hors règles de contrôle (attributs métier à confirmer — WZM) | À définir avec le métier | Élevée — attributs métier à obtenir |
| **CAL-8** — Disponibilité des DAGs cœur ventes/stock (flux GOLD → RELEX) | Technique | 1 | Haute | Les 7 DAGs Airflow qui alimentent RELEX en ventes et stock se sont-ils exécutés avec succès sur leur dernier passage ? | Statut du dernier run (API Airflow) des 7 DAGs cœur du flux ②, agrégé en pire cas | ≥ 1 DAG en échec | Faible — statut déjà disponible via l'API Airflow |
| **CAL-9** — Taux de succès des DAGs référentiel (flux GOLD → RELEX) | Technique | 2 | Moyenne | Les 21 DAGs qui alimentent le référentiel RELEX (produits, sites, fournisseurs, campagnes, calendriers) se sont-ils exécutés avec succès ? | Part des 21 DAGs référentiel du flux ② dont le dernier run est en succès | < 100 % en succès — tendance à surveiller, pas une alerte immédiate | Faible |

### 6.3 Transmission RELEX → GOLD

| Indicateur | Type | Niv. | Priorité | Description | Mesure | Seuil d'alerte | Complexité |
|---|---|---|---|---|---|---|---|
| **TRA-1** — Taux de succès du flux « Order Proposals » | Technique | 1 | Haute | Propositions émises réellement reçues/acquittées. | Reçues / émises, rapprochées par cycle (3 passages/j) | Écart émis/reçu, ou passage manquant | Moyenne |
| **TRA-2** — Latence de transmission unitaire | Technique | 1 | Moyenne | Délai émission → réception GOLD. | Écart horodatages, par message | À calibrer après observation | Moyenne |
| **TRA-3** — Taux de rejets techniques à l'interface | Technique | 2 | Moyenne | Erreurs de mapping ou timeouts. | Nb rejets / messages reçus, par cause | À calibrer (référence à établir) | Moyenne |
| **TRA-4** — Taux de transformation proposition → commande | Fonctionnel | 2 | Haute | Chaque proposition aboutit-elle à une commande exploitable ? | Commandes créées / propositions reçues, même cycle | < 100 % transformées sur le cycle | Moyenne |
| **TRA-5** — Délai réception → création de commande | Fonctionnel | 2 | Basse | Fluidité du traitement métier GOLD. | Écart horodatages, médiane | À calibrer après observation | Moyenne |
| **TRA-6** — Disponibilité des DAGs RELEX → GOLD | Technique | 1 | Haute | Les 4 DAGs qui remontent les propositions RELEX (Order Proposals, Reserve Order Proposals, projections, stock DLC) se sont-ils exécutés avec succès ? | Statut du dernier run des 4 DAGs du flux ③, agrégé en pire cas | ≥ 1 DAG en échec | Faible — statut déjà disponible ; ne résout pas l'incertitude sur la nature du flux (§4, flux ③) |

### 6.4 GOLD → WMS — Infolog/Generix (cut-off par enseigne)

| Indicateur | Type | Niv. | Priorité | Description | Mesure | Seuil d'alerte | Complexité |
|---|---|---|---|---|---|---|---|
| **WMS-1** — Taux de succès de l'import WMS | Technique | 1 | Haute | Commandes importées avec succès. | Importées / envoyées, par interface et passage | < 100 % importées sur un passage | Moyenne |
| **WMS-2** — Disponibilité du canal d'échange GOLD → WMS | Technique | 1 | Haute | Connecteur opérationnel ? | Statut du canal + statut `wms-schedule-dag` | Échec de connexion, ou passage non exécuté | Faible — statut DAG déjà disponible |
| **WMS-3** — Disponibilité du service WMS | Technique | 1 | Haute | WMS up / dégradé / down. | Interface à qualifier avec IDL ; à défaut, acquittements sur la fenêtre | Statut ≠ « up », ou aucun acquittement | Élevée — interface à qualifier |
| **WMS-4** — Durée du traitement d'import côté WMS | Technique | 1 | Moyenne | Réception → intégration WMS. | Écart envoi/acquittement, par lot | À calibrer après observation | Élevée — instrumentation à obtenir |
| **WMS-5** — Taux d'erreur ou de timeout de l'import WMS | Technique | 1 | Haute | Échecs techniques à l'import. | Part de messages en erreur/sans acquittement, par cause | Tout message en erreur/sans acquittement | Moyenne |
| **WMS-6** — Respect des règles de cut-off par enseigne | Fonctionnel | 1 | Haute | Commande après cut-off = risque non-expédition jour même. | Heure d'émission vs cut-off enseigne | Toute commande émise après cut-off | Moyenne — paramétrage à récupérer |
| **WMS-7** — Taux de commandes bloquées ou en attente côté WMS | Fonctionnel | 2 | Moyenne | Reçues mais non lancées en préparation. | Nb en statut bloqué/attente, à heure fixe, avec ancienneté | À définir avec l'exploitation | Moyenne |
| **WMS-8** — Complétude des données transmises | Fonctionnel | 2 | Moyenne | Champs obligatoires manquants (BU, fournisseur, article, quantité, dates, magasin/entrepôt, ID proposition RELEX). | Part de messages avec champ manquant | Tout champ obligatoire manquant | Faible |
| **WMS-9** — Taux de succès des DAGs interfaces GOLD → WMS | Technique | 1 | Haute | Les 9 DAGs d'interface déclenchés par l'orchestrateur (m10 à m91) se sont-ils exécutés avec succès, en complément du statut de l'orchestrateur lui-même (WMS-2) ? | Statut du dernier run des 9 DAGs `wms-write-spool-m10-dag` à `m91-dag`, agrégé en pire cas | ≥ 1 DAG en échec | Faible |

### 6.5 Flux direct RELEX ↔ WMS (angle mort prioritaire, à instrumenter)

| Indicateur | Type | Niv. | Priorité | Description | Mesure | Seuil d'alerte | Complexité |
|---|---|---|---|---|---|---|---|
| **DIR-1** — Disponibilité et fiabilité du flux direct | Technique | 1 | Haute | Flux SaaS↔SaaS hors GOLD, hors supervision aujourd'hui. | Prérequis : qualifier la technologie avec RELEX (WZM) et IDL, puis statut succès/échec et délai | À définir une fois le flux qualifié | Élevée — flux non qualifié |
| **DIR-2** — Nature et contenu des données échangées | Fonctionnel | 2 | Haute | Capacité entrepôt, créneaux, retours logistiques ? | Cartographie des échanges (émetteur, destinataire, objet, fréquence) | Sans objet (livrable de cartographie) | Moyenne — atelier RELEX/IDL |
| **DIR-3** — Volume et fréquence du flux | Technique | 2 | Moyenne | Rythme temps réel ou batch, non qualifié à ce stade. | Nb d'échanges et volumétrie, une fois qualifié | Sans objet à ce stade | Moyenne |

### 6.6 Indicateurs de bout en bout (transverses)

| Indicateur | Type | Niv. | Priorité | Description | Mesure | Seuil d'alerte | Complexité |
|---|---|---|---|---|---|---|---|
| **E2E-1** — Lead time global (collecte → ordre WMS) | Fonctionnel | 2 | Haute | Temps entre remontée des ventes et ordre de préparation. | Écart 1er événement collecte / acquittement WMS, décomposé par étape | Dépassement de la fenêtre cible (à définir) | Élevée — corrélation inter-systèmes requise |
| **E2E-2** — Traçabilité de l'identifiant de proposition RELEX | Technique | 1 | Haute | Une même commande suivie de RELEX à GOLD puis WMS ? | Part de commandes retrouvées avec même identifiant dans les 3 systèmes | < 100 % traçables de bout en bout | Élevée — identifiant de corrélation à mettre en place |
| **E2E-3** — Disponibilité simultanée de RELEX, GOLD et WMS | Technique | 1 | Moyenne | Chaîne disponible dans son ensemble à l'instant T ? | Part de temps où les 3 health-checks sont simultanément OK | ≥ 1 système indisponible | Moyenne |
| **E2E-4** — Taux de cycles nominaux sans recours au secours | Fonctionnel | 2 | Moyenne | Part des cycles sans activation du flux de secours RELEX. | Cycles sans secours / total, par période | Toute activation du flux de secours | Faible |
| **E2E-5** — Taux d'incidents nécessitant une intervention manuelle | Fonctionnel | 2 | Haute | Incidents exigeant une intervention humaine, et à quelle étape. | Nb interventions déclarées / étape, rapporté aux cycles | À définir avec l'exploitation | Faible |

---

## 7. Points à clarifier avant industrialisation

1. **Portée de l'API OTel RELEX** : infrastructure seule, ou attributs métier (statut de proposition, magasin, DLC) dans les spans ? À confirmer avec RELEX (WZM) — conditionne la richesse du Niveau 2.
2. **Instrumentation GOLD** (on-premises) : pas de traçage OTel natif. À trancher : agent OTel côté serveur, ou supervision limitée aux logs applicatifs.
3. **Instrumentation WMS** : à qualifier avec l'intégrateur IDL. Sans API de supervision, le Niveau 1 se limite aux statuts d'import côté GOLD.
4. **Flux direct RELEX ↔ WMS** (§4, §6.5) : nature technique et contenu métier non qualifiés — **priorité n°1**, échappe entièrement à la supervision construite autour de GOLD.
5. **Batch nocturne O4HQ → GOLD** (flux ①) : hors Airflow, sans alerte en cas d'échec — **priorité n°2**, point de contrôle à définir avec GOLD.
6. **Corrélation trans-systèmes** : propager un identifiant de corrélation (trace ID) entre RELEX, GOLD, WMS est-il un objectif du pilote, ou se limite-t-on à des métriques par système ?
7. **Boucle retour WMS → GOLD** (flux ⑦) : à inclure ou non dans le pilote. Sans elle, on supervise l'émission de l'ordre mais pas son exécution.

---

## 8. Maquette de tableau de bord (Grafana / Prometheus)

Vue de pilotage en 3 blocs (valeurs fictives d'exemple) :

**L'essentiel du jour**
- Magasins servis à temps : 97,4 % (1 483/1 522, objectif 99 %)
- Commandes parties à l'heure : 99,7 % (2 en retard)
- Chaîne disponible : 99,2 % (aucune coupure hier)
- Durée du cycle : 4h12 (objectif 6h)
- Cycles sans incident : 96 % (48/50)
- Interventions manuelles : 3 (▲ +1 vs hier, objectif 0)

**Où en est la chaîne ?**
- Remontée des ventes — Conforme (terminée à 04:41, 4 magasins à rattraper)
- Calcul du réassort — À surveiller (1 calcul repris en secours, propositions livrées à 99 %)
- Transmission des commandes — Conforme (3/3 envois reçus, 12 messages repris)
- Envoi à l'entrepôt — En écart (Carrefour Hyper : 2 commandes après cut-off 06:30)
- Échange direct hors GOLD — Non suivi (aucune mesure disponible, chantier prioritaire)
- Si une étape s'arrête → rupture en rayon (impact fort)

**Ce qui demande une décision**
- À trancher : expédier aujourd'hui ou demain (2 commandes Carrefour Hyper)
- À surveiller : calcul repris en secours (2 fois cette semaine)
- À lancer : mesurer l'échange direct (aucune visibilité à ce jour)

Principe : aucun code technique à l'écran — chaque tuile alimentée par les indicateurs du §6, seul le chiffre, la couleur et la décision comptent. **Seuils de couleur à calibrer après une période d'observation.**

---

## 9. Architecture de la solution

Personne ne va chercher les indicateurs à la main : deux serveurs **MCP** donnent un accès en lecture à ce que chaque système sait de lui-même. Un **agent hébergé dans Azure** les interroge à intervalle régulier, calcule les indicateurs du §6, en déduit les indicateurs chapeau du §5 et alimente le tableau de bord du §8.

Le découpage suit la frontière technique du parc : GOLD est on-premises (datacenter LabelVie), RELEX et le WMS Generix sont en SaaS. Un serveur MCP reste donc dans le datacenter LabelVie au contact de GOLD ; l'autre est déployé dans Azure, au plus près des API éditeurs. Les deux réseaux sont reliés par un **VPN site à site**.

### 9.1 Composants

| Composant | Emplacement | Rôle | Accès accordé |
|---|---|---|---|
| **Serveur MCP GOLD** | Datacenter LabelVie, on-premises | Accès à l'état des traitements GOLD : fin des batchs, tables d'interface, statuts d'import, comptages par magasin/enseigne. | Compte de service Oracle en lecture seule, sur vues dédiées |
| **Serveur MCP RELEX et Generix** | Azure, Container Apps | Interroge les API des deux éditeurs : traces OpenTelemetry (RELEX), statuts d'import/acquittements (WMS). | Clés API dédiées supervision, portée lecture |
| **Agent de supervision** | Azure, Container Apps | Appelle les deux serveurs MCP, calcule les indicateurs unitaires puis chapeau, publie les séries. | Identité managée Azure ; aucun accès direct aux bases ni applications |
| **Prometheus** | Azure Monitor (service managé) | Stocke les séries temporelles, évalue les règles d'alerte. | Ingestion depuis l'agent uniquement |
| **Grafana** | Azure (service managé) | Affiche le tableau de bord du §8, route les alertes. | Lecture seule sur Prometheus, authentification Entra ID |
| **Liaison réseau** | VPN site à site IPsec | Relie le VNet Azure au datacenter LabelVie. | Un seul flux autorisé, Azure → serveur MCP GOLD, port unique |

### 9.2 Schéma de déploiement (zones)

```
┌─────────────────────────┐        ┌──────────────┐        ┌───────────────────────────────┐
│   Datacenter LabelVie    │  VPN   │              │        │             Azure               │
│  ┌────────────────────┐ │ IPsec  │              │        │  ┌───────────────────────────┐  │
│  │  GOLD (Oracle)      │◀┼────────┼──────────────┼───F1c──┼─▶│  Serveur MCP GOLD (relais)  │  │
│  │  + Airflow          │ │        │              │        │  └──────────┬──────────────────┘  │
│  └────────────────────┘ │        │  Tunnel IKEv2 │        │             │F1b                    │
│                          │        │  ESP/AES-256  │        │  ┌──────────▼──────────────────┐  │
└─────────────────────────┘        └──────────────┘        │  │   Agent de supervision       │  │
                                                              │  │   (Container Apps)           │  │
     SaaS éditeurs                                            │  └───┬──────────┬──────────┬────┘  │
┌─────────────────────────┐                                  │      │F1a       │F2        │F4      │
│ RELEX (OTel API)         │◀────────F0a───────────────────────┼──┐   │          │          │        │
│ WMS Infolog/Generix      │◀────────F0b───────────────────────┼──┤   │          │          │        │
└─────────────────────────┘                                   │  │   │  ┌───────▼──┐ ┌─────▼─────┐  │
                                                                │  └──▶│MCP RELEX/  │ │ Prometheus │  │
                                                                │      │Generix     │ │ (Az.Monitor)│  │
                                                                │      └────────────┘ └─────┬──────┘  │
                                                                │                     F3│Grafana      │
                                                                │                            │Key Vault│
                                                                └───────────────────────────────────────┘
```

*Repères F0 à F4 : flux de supervision (détail §9.3). Numéros entourés ①–⑦ : flux métier (§4).*

### 9.3 Détail technique des flux

| Flux | Sens | Protocole / port | Authentification | Format | Rythme |
|---|---|---|---|---|---|
| **F0a** | MCP Azure → API RELEX | HTTPS REST + OTLP, port 443 | OAuth2 client credentials + clé API supervision | JSON (REST), protobuf (spans OTLP) | À chaque appel de l'agent |
| **F0b** | MCP Azure → API WMS Generix Infolog | HTTPS REST, port 443 *(interface à confirmer avec IDL)* | Clé API dédiée supervision | JSON ou XML selon l'interface | À chaque appel de l'agent |
| **F1a** | Agent → MCP RELEX/Generix | HTTP/2 sur TLS 1.2+, port 443 | Jeton Entra ID (identité managée) | JSON, protocole MCP | Toutes les minutes |
| **F1b** | Agent → MCP GOLD, via VPN | HTTPS 443, encapsulé IPsec | Jeton Entra ID + certificat serveur interne | JSON, protocole MCP | Toutes les minutes |
| **F1c** | MCP GOLD → base Oracle GOLD | Oracle Net / TCP, port 1521 | Compte de service lecture seule, chiffrement Oracle natif à activer | Résultats SELECT sur vues dédiées | À chaque appel de l'agent |
| **F1d** | MCP GOLD → API Airflow | HTTPS REST, port à confirmer avec GOLD | Jeton de service Airflow, lecture | JSON | À chaque appel de l'agent |
| **F2** | Agent → Prometheus | Remote write HTTP POST sur TLS, port 443 | Jeton Entra ID | Protobuf compressé Snappy | Toutes les 60 secondes |
| **F3** | Grafana → Prometheus | HTTPS, requêtes PromQL, port 443 | Entra ID, lecture seule | JSON | À l'affichage / évaluation des alertes |
| **F4** | Agent → Azure Key Vault | HTTPS, port 443 | Identité managée, politique de lecture des secrets | JSON | Au démarrage et à chaque rotation de clé |
| **Tunnel** | Datacenter LabelVie ↔ VNet Azure | IPsec IKEv2, UDP 500/4500, ESP | AES-256, clés portées par les passerelles | — | Permanent |
| **⑤** | RELEX → WMS (hors GOLD) | Non qualifié à ce jour | Non qualifié | Non qualifié | Sans objet à ce stade |

### 9.4 Cadre de sécurité — un périmètre volontairement étroit

Un agent qui lit des systèmes de production doit être **incapable de leur nuire**, même en cas d'erreur. La supervision ne peut rien modifier ; elle ne voit que ce qui lui est explicitement ouvert.

- **Lecture seule partout** : comptes de service GOLD en lecture sur vues dédiées ; clés API RELEX/Generix en portée lecture ; aucun droit d'écriture.
- **Outils MCP limités par liste blanche** : chaque serveur n'expose que les opérations nécessaires aux indicateurs du §6, nommées une par une. Pas de requête libre, pas d'exécution de code, pas d'accès au système de fichiers.
- **Agent sans autonomie d'action** : lit, calcule, publie des séries. Ne relance rien, ne corrige rien, n'envoie aucune commande. Toute remédiation reste une décision humaine.
- **Cloisonnement réseau** : serveurs MCP et agent dans un VNet dédié, sans exposition publique. Le VPN n'autorise qu'un seul flux, Azure → MCP GOLD, port unique.
- **Identités et secrets gérés** : authentification par identité managée Azure ; clés API dans Azure Key Vault, rotation régulière ; aucun secret dans le code.
- **Garde-fous d'exécution** : délais d'attente, plafond d'appels par minute, quotas par outil — un défaut de l'agent ne doit jamais devenir une charge pour la production.
- **Traçabilité** : chaque appel MCP journalisé (horodatage, outil, appelant, durée, volume) — traçabilité complète de ce que la supervision a lu, et quand.

> Cette architecture ne corrige rien : elle rend le processus lisible et déclenche la bonne alerte au bon moment. L'action reste du ressort de l'exploitation et du métier.

---

## 10. Prochaines étapes

- [ ] Trancher les 7 points de clarification du §7 avec les équipes GOLD, RELEX (WZM) et l'intégrateur IDL
- [ ] Qualifier techniquement le flux direct RELEX ↔ WMS (§6.5) — priorité n°1
- [ ] Définir le point de contrôle du batch nocturne O4HQ → GOLD (§6.1, COL-1) — priorité n°2
- [ ] Développer le serveur MCP GOLD (liste blanche d'outils sur vues Oracle dédiées)
- [ ] Développer le serveur MCP RELEX/Generix (Container Apps)
- [ ] Développer l'agent de supervision (calcul unitaires → chapeau → publication Prometheus)
- [ ] Calibrer les seuils marqués « à calibrer après observation » sur une période pilote
- [ ] Construire le tableau de bord Grafana (§8) et les règles d'alerte

---

*Document de spécifications — MonitoringAgent — Version 1.1 — Août 2026*
*Source : Note d'Architecture — Métriques de supervision Order Management, LabelVie / Pôle TECH, V1.0, 28/07/2026.*
