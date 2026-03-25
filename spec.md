# MyBooking App — Spécifications Fonctionnelles

## 1. Vision du produit

MyBooking App est une plateforme d'agrégation intelligente qui permet à l'utilisateur, via des critères simples, de **comparer en temps réel** toutes les grandes plateformes de réservation d'hébergement (hôtels, appartements, chambres d'hôtes) et de **trouver le meilleur moyen de transport** (train, avion, bateau, bus, voiture) pour son voyage.

---

## 2. Utilisateurs cibles

| Profil | Description |
|---|---|
| Voyageur loisir | Particulier cherchant la meilleure offre prix/confort |
| Voyageur affaires | Professionnel avec contraintes horaires strictes |
| Famille | Besoin de logements spacieux et transports groupés |
| Backpacker | Budget serré, flexibilité maximale sur les dates |

---

## 3. Critères de recherche (saisie utilisateur)

### 3.1 Hébergement

- **Destination** : ville, région ou pays
- **Dates** : date d'arrivée et de départ (ou durée en nuits)
- **Nombre de voyageurs** : adultes, enfants (âges)
- **Type d'hébergement** : hôtel, appartement, chambre d'hôtes, auberge de jeunesse, villa
- **Budget maximum** : par nuit ou total du séjour
- **Équipements souhaités** : Wi-Fi, parking, piscine, cuisine équipée, animaux acceptés, etc.
- **Note minimale** : étoiles ou score de satisfaction (ex. ≥ 4/5)
- **Annulation gratuite** : oui / non / indifférent

### 3.2 Transport

- **Ville de départ**
- **Date et heure de départ souhaitées** (ou plage horaire)
- **Flexibilité de dates** : ±1 jour, ±3 jours, semaine entière
- **Modes de transport acceptés** : train, avion, bateau, bus longue distance, voiture de location, covoiturage
- **Budget maximum transport** : par personne ou total
- **Priorité** : prix le plus bas / durée la plus courte / empreinte carbone minimale
- **Nombre de correspondances max** : 0 (direct), 1, 2, indifférent
- **Bagages** : cabine uniquement, soute, pas de bagage

---

## 4. Plateformes interrogées

### 4.1 Hébergement

| Plateforme | Type |
|---|---|
| Booking.com | Hôtels, appartements, B&B |
| Airbnb | Appartements, maisons privées |
| Expedia | Hôtels, packages |
| Hotels.com | Hôtels |
| Trivago | Agrégateur hôtels |
| Hostelworld | Auberges de jeunesse |
| Vrbo | Locations vacances familiales |
| Abritel | Locations vacances (France) |
| Le Bon Coin Vacances | Locations particuliers |
| Leboncoin | Locations particuliers |
| Gîtes de France | Hébergements ruraux |

### 4.2 Transport

| Plateforme / Service | Mode |
|---|---|
| SNCF Connect / Rail Europe | Train (France / Europe) |
| Trainline | Train (international) |
| Skyscanner | Avion |
| Google Flights | Avion |
| Kayak | Avion, train, voiture |
| Flixbus | Bus longue distance |
| BlaBlaCar | Covoiturage |
| Corsair / Brittany Ferries / DFDS | Bateau / Ferry |
| Rentalcars | Location de voiture |
| Kiwi.com | Combinaison vols low-cost |

---

## 5. Fonctionnalités principales

### 5.1 Recherche unifiée

- Un seul formulaire de saisie pour hébergement + transport
- Lancement simultané des requêtes sur toutes les plateformes (requêtes parallèles)
- Temps de réponse cible : < 5 secondes pour les premiers résultats (affichage progressif)

### 5.2 Résultats hébergement

- Liste triable par : prix, note, distance centre-ville, popularité
- Filtres dynamiques applicables après recherche
- Affichage : carte + liste
- Comparaison côte à côte de 2 à 4 hébergements
- Lien direct vers la plateforme d'origine pour finaliser la réservation
- Indicateur de disponibilité en temps réel

### 5.3 Résultats transport

- Liste triable par : prix total, durée, nombre d'escales, empreinte CO₂
- Comparaison multi-modes sur un même trajet (ex. TGV vs avion vs bus)
- Affichage d'un score global combinant prix, durée et impact environnemental
- Regroupement des offres par mode de transport
- Alerte prix : notification si le prix d'une option baisse

### 5.4 Vue combinée (Package)

- Proposition de **combinaisons optimales** hébergement + transport
- Score global de l'offre : prix total, durée de trajet, confort, écologie
- Tri par meilleur rapport qualité/prix global

### 5.5 Compte utilisateur (optionnel)

- Sauvegarde des recherches et des favoris
- Historique des voyages
- Alertes personnalisées (baisse de prix, disponibilité)
- Profil de préférences (mode de transport favori, équipements récurrents)

---

## 6. Algorithme de recommandation

### 6.1 Score hébergement

```
Score = (Note / 5) × 40 + (1 - Prix/Budget) × 40 + BonusEquipements × 20
```

- Note : note moyenne des avis (pondérée par le nombre d'avis)
- Prix/Budget : ratio du prix par rapport au budget max renseigné
- BonusEquipements : nombre d'équipements souhaités présents / total souhaité

### 6.2 Score transport

```
Score = (1 - Prix/BudgetTransport) × 35 + (1 - Durée/DuréeMax) × 35 + (1 - CO₂/CO₂Max) × 30
```

- Durée max de référence : durée du mode le plus lent sur le trajet
- CO₂ max de référence : empreinte du mode le plus polluant sur le trajet

### 6.3 Score combiné (package)

```
ScorePackage = ScoreHébergement × 0.5 + ScoreTransport × 0.5
```

Paramètres ajustables par l'utilisateur via des curseurs de pondération.

---

## 7. Architecture technique (cible)

```
┌─────────────────────────────────────────────────────┐
│                  Frontend (Web / Mobile)            │
│         React Native / Next.js — PWA                │
└──────────────────────┬──────────────────────────────┘
                       │ REST / GraphQL
┌──────────────────────▼──────────────────────────────┐
│                  API Gateway                        │
│         Auth · Rate Limiting · Caching              │
└──────┬──────────────────────────┬───────────────────┘
       │                          │
┌──────▼──────┐          ┌────────▼────────┐
│ Service     │          │ Service         │
│ Hébergement │          │ Transport       │
│ (agrégateur)│          │ (agrégateur)    │
└──────┬──────┘          └────────┬────────┘
       │                          │
┌──────▼──────────────────────────▼────────┐
│         Connecteurs Plateformes          │
│  (APIs officielles + scraping éthique)  │
└──────────────────────────────────────────┘
       │                          │
┌──────▼──────┐          ┌────────▼────────┐
│   Cache     │          │   Base de       │
│   Redis     │          │   données       │
│             │          │   PostgreSQL    │
└─────────────┘          └─────────────────┘
```

### Stack technologique recommandée

| Couche | Technologie |
|---|---|
| Frontend Web | Next.js 14 (React) |
| Frontend Mobile | React Native / Expo |
| Backend | Node.js + NestJS ou Python FastAPI |
| Cache | Redis |
| Base de données | PostgreSQL |
| File de messages | RabbitMQ / BullMQ |
| Hébergement | AWS / GCP / Vercel |
| CI/CD | GitHub Actions |

---

## 8. Intégrations API

### 8.1 Approche d'intégration

- **APIs officielles** (priorité 1) : utiliser les programmes partenaires officiels (Booking.com Affiliate, Skyscanner API, Amadeus, etc.)
- **Agrégateurs tiers** (priorité 2) : RapidAPI, Travelpayouts pour les plateformes sans API directe
- **Scraping éthique** (priorité 3, dernier recours) : uniquement si autorisé par les CGU, avec respect du fichier `robots.txt` et des délais entre requêtes

### 8.2 Gestion des quotas et erreurs

- Retry automatique avec backoff exponentiel (2s, 4s, 8s, 16s)
- Fallback : afficher les résultats des plateformes disponibles si l'une est hors ligne
- Mise en cache des résultats : 10 minutes pour les prix, 24h pour les métadonnées (photos, descriptions)

---

## 9. Expérience utilisateur (UX)

### 9.1 Parcours principal

```
1. Accueil → Formulaire de recherche simple
2. Résultats → Affichage progressif hébergement + transport
3. Détail → Fiche complète d'un hébergement ou transport
4. Comparaison → Vue côte à côte jusqu'à 4 offres
5. Sélection → Redirection vers la plateforme partenaire pour réservation
```

### 9.2 Design principles

- **Simplicité** : 3 champs obligatoires maximum pour lancer une recherche (destination, dates, voyageurs)
- **Rapidité** : skeleton loading, affichage progressif des résultats
- **Transparence** : toujours indiquer la source du prix et la date de mise à jour
- **Accessibilité** : WCAG 2.1 AA minimum

---

## 10. Sécurité et conformité

- **RGPD** : consentement explicite, droit à l'oubli, données hébergées en EU
- **Authentification** : OAuth 2.0 / JWT
- **Données sensibles** : aucune carte bancaire stockée (redirection vers plateforme partenaire)
- **HTTPS** obligatoire sur tous les endpoints
- **Rate limiting** : protection contre les abus d'API

---

## 11. Indicateurs de performance (KPIs)

| Indicateur | Cible |
|---|---|
| Temps de réponse (premiers résultats) | < 5 secondes |
| Taux de disponibilité | 99,9 % |
| Taux de conversion (clic vers réservation) | > 15 % |
| Couverture plateformes hébergement | ≥ 8 plateformes |
| Couverture modes de transport | ≥ 5 modes |
| Note utilisateur (App Store / Play Store) | ≥ 4,5 / 5 |

---

## 12. Roadmap

### Phase 1 — MVP (mois 1 à 3)
- [ ] Formulaire de recherche simplifié
- [ ] Intégration de 3 plateformes hébergement (Booking.com, Airbnb, Expedia)
- [ ] Intégration de 2 modes de transport (avion via Skyscanner, train via Trainline)
- [ ] Affichage liste des résultats avec tri basique
- [ ] Lien de redirection vers la plateforme source

### Phase 2 — Enrichissement (mois 4 à 6)
- [ ] Ajout de 5 plateformes hébergement supplémentaires
- [ ] Ajout de 3 modes de transport (bus, ferry, covoiturage)
- [ ] Vue cartographique des hébergements
- [ ] Comparaison côte à côte
- [ ] Compte utilisateur et favoris

### Phase 3 — Intelligence (mois 7 à 9)
- [ ] Algorithme de score et recommandation
- [ ] Vue combinée package hébergement + transport
- [ ] Alertes prix personnalisées
- [ ] Application mobile (iOS / Android)
- [ ] Score d'empreinte carbone

### Phase 4 — Optimisation (mois 10 à 12)
- [ ] Personnalisation basée sur l'historique
- [ ] Internationalisation (EN, ES, DE, IT)
- [ ] Programme d'affiliation et monétisation
- [ ] API publique pour partenaires

---

## 13. Monétisation

| Modèle | Description |
|---|---|
| Commission d'affiliation | Pourcentage sur chaque réservation générée (3–10 %) |
| Placement sponsorisé | Mise en avant d'offres partenaires (clairement labelisée) |
| Abonnement Premium | Alertes illimitées, comparaisons avancées, sans publicité |
| API B2B | Accès à l'agrégateur pour agences ou autres apps |

---

*Document de spécifications — Version 1.0 — Mars 2026*
