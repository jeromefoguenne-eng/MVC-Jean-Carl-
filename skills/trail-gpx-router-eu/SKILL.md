---
name: trail-gpx-router-eu
description: "Conçoit, calcule et audite des tracés GPX de trail et randonnée en Europe en tenant compte des chemins autorisés ou interdits (OpenStreetMap Overpass, OpenRouteService, BRouter, Natura 2000 et réserves naturelles)."
---

# Trail GPX Router & Audit d'Accès (Europe)

Cette compétence permet de concevoir des tracés GPX pour le trail et la randonnée en Europe tout en vérifiant la légalité et l'accessibilité des chemins empruntés (chemins publics, sentiers balisés, restrictions saisonnières, propriétés privées et zones protégées).

## 1. Sources de Données Territoriales (Europe)

### A. OpenStreetMap (OSM) — Référentiel de base
Les droits de passage et la nature des sentiers sont encodés sur les tronçons (`highway=path`, `footway`, `track`, `bridleway`, `cycleway`) via les attributs suivants :

| Tag OSM | Valeurs clés | Signification pour le trail |
| :--- | :--- | :--- |
| `access` | `yes`, `permissive`, `private`, `no` | Droit d'accès général. `private` et `no` interdisent le passage. |
| `foot` | `designated`, `yes`, `permissive`, `no` | Autorisation piétonne spécifique (`designated` = sentier officiel). |
| `access:conditional` | `no @ (Nov 01-Jun 14)`, etc. | Fermeture saisonnière (chasse, nidification, dégel). |
| `sac_scale` | `hiking` (`T1`) à `difficult_alpine_hiking` (`T6`) | Cotation alpine de difficulté technique. |
| `trail_visibility` | `excellent`, `good`, `intermediate`, `bad`, `no` | Visibilité réelle du sentier sur le terrain. |
| `boundary=protected_area` | `protected_area=*`, `protection_title=Natura 2000` | Périmètres de réserves naturelles, parcs nationaux ou zones Natura 2000. |

### B. Couches Réglementaires Nationales Complémentaires
OSM ne reflète pas toujours instantanément les arrêtés locaux. En cas de doute, croiser avec :
* **Union Européenne** : Périmètres **Natura 2000** (Agence européenne pour l'environnement).
* **Belgique / Wallonie** : **WalOnMap (Géoportail de Wallonie)** — Atlas des voiries vicinales (chemins/sentiers communaux légaux) et zones DNF / réserves naturelles.
* **France** : **IGN Géoportail** (BD TOPO, zones cœur des parcs nationaux, réserves naturelles nationales/régionales, arrêtés préfectoraux).

---

## 2. Arbre de Décision : Tracer et Valider un GPX

1. **Besoin de calculer un nouvel itinéraire entre points de passage** :
   * Utiliser **OpenRouteService (ORS)** avec le profil `foot-hiking` (exclut nativement `access=no` et `foot=no`, respecte `access:conditional` et fournit l'élévation en export GPX).
   * Ou utiliser **BRouter** avec un profil `.brf` personnalisé (`hiking-beta.brf` ou `trekking.brf`) pour pénaliser les chemins `permissive`, bannir `private`/`no` et favoriser les réseaux balisés officiels (`route=foot`, GR, PR).
2. **Besoin de vérifier un fichier `.gpx` existant** :
   * Exécuter le script d'audit boîte noire `scripts/audit_gpx_access.py` (consulter d'abord `python scripts/audit_gpx_access.py --help`).
   * Analyser le rapport produit :
     * **Feu Vert (`AUTORISE`)** : `foot=yes/designated` ou `access=yes` sans restriction.
     * **Vigilance (`CONDITIONNEL` / `ZONE_PROTEGEE`)** : `access:conditional`, `permissive` ou traversée d'une `boundary=protected_area` (vérifier les dates de chasse/nidification ou la réglementation du parc).
     * **Blocage (`INTERDIT_OU_PRIVE`)** : `access=no`, `access=private`, `foot=no` -> **Contourner obligatoirement le tronçon** avant de valider la trace finale.

---

## 3. Utilisation du Script d'Audit GPX (`scripts/audit_gpx_access.py`)

> [!TIP]
> Toujours lancer `--help` avant utilisation pour vérifier les options disponibles sans charger le code source complet en contexte.

```bash
python scripts/audit_gpx_access.py --help
python scripts/audit_gpx_access.py --gpx chemin/vers/trace.gpx --sample-step 5
```

* Le script échantillonne les points du GPX, interroge l'API publique **Overpass (OpenStreetMap)** sur la boîte englobante du parcours et identifie les chemins et zones protégées à proximité de la trace.
* Il n'utilise aucune clé API et ne repose que sur la bibliothèque standard Python 3.

---

## 4. Règles de Qualité & Sécurité

1. **Respect de l'API Overpass** : Ne pas multiplier les requêtes simultanées ; utiliser `--sample-step` (par défaut `5` points) et un rayon de recherche raisonnable (`--radius 35` mètres).
2. **Export GPX propre** : Vérifier que les balises `<trkpt lat="..." lon="...">` et `<ele>` sont valides et ordonnées chronologiquement/géographiquement.
3. **Avertissement terrain** : Un tracé validé numériquement reste soumis à la signalisation locale (panneaux de battue de chasse, éboulements, arrêtés communaux temporaires).
