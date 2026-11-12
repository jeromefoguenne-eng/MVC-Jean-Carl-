---
name: trail-gpx-router-eu
description: "Conçoit, calcule et audite des tracés GPX de moto trail (off-road / tout-terrain légal) en Europe en tenant compte des chemins autorisés ou interdits aux véhicules motorisés (OpenStreetMap Overpass, BRouter, Natura 2000, Code forestier, Loi Lalonde)."
---

# Trail Moto GPX Router & Audit d'Accès Motorisé (Europe)

Cette compétence permet de concevoir et d'auditer des tracés GPX pour la **moto trail / tout-terrain (dual-sport)** en Europe en vérifiant la légalité de la circulation motorisée sur chaque chemin, piste ou sentier.

> [!WARNING]
> En Europe, un chemin ouvert aux piétons ou aux VTT (`foot=yes`, `highway=path`, `highway=track`) est **très souvent interdit aux motos** (Code forestier en Belgique/Wallonie, Loi Lalonde en France, réserves naturelles, arrêtés communaux). Ne jamais se fier aux tags piétons.

---

## 1. Sources de Données Territoriales (Moto Trail en Europe)

### A. OpenStreetMap (OSM) — Référentiel d'accès motorisé
Les droits de passage pour les motos reposent sur les attributs suivants :

| Tag OSM | Valeurs clés | Signification pour la moto trail |
| :--- | :--- | :--- |
| `motorcycle` | `yes`, `designated`, `permissive`, `no`, `private` | Droit d'accès spécifique aux motos (prioritaire sur `motor_vehicle` et `access`). |
| `motor_vehicle` | `yes`, `permissive`, `no`, `private`, `forestry`, `agricultural`, `destination` | Droit d'accès des véhicules à moteur. `forestry`, `agricultural` et `destination` interdisent le loisir/transit. |
| `vehicle` / `access` | `yes`, `no`, `private`, `forestry`, `agricultural` | Règle générale si `motorcycle` et `motor_vehicle` sont absents. |
| `motor_vehicle:conditional` / `motorcycle:conditional` | `no @ (...)`, `yes @ (...)` | Fermetures saisonnières (chasse, risque incendie massif forestier, période estivale). |
| `highway` | `track`, `unclassified`, `service`, `path`, `bridleway`, `footway`, `cycleway` | `path`, `footway`, `cycleway`, `bridleway` sont **interdits par défaut** aux motos sauf autorisation explicite. |
| `tracktype` | `grade1` (dur) à `grade5` (très meuble/herbeux) | État de portance de la piste pour adapter au gabarit de la moto (gros trail vs enduro). |
| `surface` / `smoothness` | `gravel`, `dirt`, `sand`, `mud`, `rock`, `unpaved` | Type de revêtement et technicité du terrain. |
| `boundary=protected_area` | `protected_area=*`, `protection_title=Natura 2000` | Zones protégées où la circulation motorisée hors voies publiques revêtues est quasi systématiquement interdite. |

### B. Couches Réglementaires Nationales Complémentaires
OSM n'étant pas opposable juridiquement, croiser systématiquement les pistes `track` non taguées avec :
* **Union Européenne** : Périmètres **Natura 2000** (Agence européenne pour l'environnement) et traces communautaires vérifiées type **Trans Euro Trail (TET)**.
* **Belgique / Wallonie** : **WalOnMap (Géoportail de Wallonie)** — Atlas des voiries vicinales et Code forestier (DNF : circulation motorisée interdite sur les chemins/sentiers forestiers non revêtus sauf autorisation expresse).
* **France** : **IGN Géoportail** + **Loi Lalonde** (interdiction hors voies ouvertes à la circulation publique ; notion de carrossabilité/voies communales et chemins ruraux non interdits par arrêté municipal ou préfectoral, zones cœur de parcs nationaux, massifs DFCI l'été).

---

## 2. Arbre de Décision : Tracer et Valider un GPX Moto Trail

1. **Calculer un itinéraire off-road légal** :
   * Privilégier **BRouter** (avec un profil moto/dual-sport personnalisé excluant `motor_vehicle=no/private/forestry/agricultural/destination`, `highway=path/footway/cycleway/bridleway`, et favorisant `highway=track` avec `tracktype=grade2..grade4` + `motor_vehicle=yes`).
   * Éviter les profils `foot-hiking` ou `mtb` qui empruntent des sentiers interdits aux engins à moteur.
2. **Auditer un fichier `.gpx` existant** :
   * Exécuter le script d'audit boîte noire `scripts/audit_gpx_access.py` (lancer d'abord `--help`).
   * Interpréter les statuts retournés :
     * **Feu Vert (`AUTORISE`)** : `motorcycle=yes` / `motor_vehicle=yes` explicite, ou voie publique (`unclassified`, `residential`, `tertiary`, etc.) sans restriction motorisée.
     * **Vigilance (`A_VERIFIER_PISTE` / `CONDITIONNEL`)** : `highway=track` sans tag `motor_vehicle` explicite (vérifier arrêté local / Code forestier), `permissive`, ou restriction `conditional`.
     * **Blocage (`INTERDIT_MOTO`)** : `motorcycle=no`, `motor_vehicle=no/private/forestry/agricultural/destination`, ou `highway=path/footway/cycleway/bridleway/pedestrian` sans autorisation moto explicite -> **Contourner obligatoirement le tronçon**.

---

## 3. Utilisation du Script d'Audit GPX (`scripts/audit_gpx_access.py`)

> [!TIP]
> Toujours lancer `--help` avant utilisation pour vérifier les options disponibles sans charger le code source complet en contexte.

```bash
python scripts/audit_gpx_access.py --help
python scripts/audit_gpx_access.py --gpx chemin/vers/trace_moto.gpx --sample-step 5
```

* Le script échantillonne les points du GPX, interroge l'API publique **Overpass (OpenStreetMap)** sur la boîte englobante du parcours, applique la logique d'accès **moto / véhicules motorisés**, et remonte également `tracktype`, `surface`, `smoothness` et les `protected_area` traversées.
* Aucune clé API requise ; bibliothèque standard Python 3 uniquement.

---

## 4. Règles de Qualité & Sécurité

1. **Respect de l'API Overpass** : Utiliser `--sample-step` (défaut `5`) et `--radius` (défaut `35` mètres) pour limiter la charge.
2. **Responsabilité terrain** : Un chemin marqué `AUTORISE` ou `A_VERIFIER_PISTE` dans OSM reste soumis à la signalisation réelle sur place (panneaux B0/C3, barrières forestières, arrêtés temporaires de chasse ou risque incendie).
