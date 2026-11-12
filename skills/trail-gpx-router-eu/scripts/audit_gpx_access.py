#!/usr/bin/env python3
"""Audit d'accessibilite moto trail d'un fichier GPX via OpenStreetMap (Overpass API)."""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

NON_MOTORIZED_HIGHWAYS = {
    "path",
    "footway",
    "cycleway",
    "bridleway",
    "pedestrian",
    "steps",
}

RESTRICTED_ACCESS_VALUES = {
    "no",
    "private",
    "forestry",
    "agricultural",
    "destination",
    "customers",
    "delivery",
}

ALLOWED_ACCESS_VALUES = {"yes", "designated", "official"}


@dataclass
class TrackPoint:
    lat: float
    lon: float
    ele: float | None = None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance en metres entre deux coordonnees WGS84."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def parse_gpx(path: str) -> list[TrackPoint]:
    """Extrait les points <trkpt> et <rtept> d'un fichier GPX."""
    tree = ET.parse(path)
    root = tree.getroot()
    points: list[TrackPoint] = []
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag in ("trkpt", "rtept"):
            lat = float(elem.attrib["lat"])
            lon = float(elem.attrib["lon"])
            ele = None
            for child in elem:
                if child.tag.split("}")[-1] == "ele" and child.text:
                    ele = float(child.text)
                    break
            points.append(TrackPoint(lat=lat, lon=lon, ele=ele))
    return points


def query_overpass(bbox: tuple[float, float, float, float], timeout: int = 30) -> dict[str, Any]:
    """Interroge Overpass pour recuperer voies, pistes, sentiers et zones protegees."""
    south, west, north, east = bbox
    query = f"""
    [out:json][timeout:{timeout}];
    (
      way["highway"~"^(track|unclassified|service|residential|tertiary|secondary|path|footway|cycleway|bridleway|pedestrian|steps)$"]({south},{west},{north},{east});
      way["boundary"="protected_area"]({south},{west},{north},{east});
      relation["boundary"="protected_area"]({south},{west},{north},{east});
    );
    out tags geom;
    """
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "trail-gpx-router-eu-moto/1.1"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def classify_way_moto(tags: dict[str, str]) -> str:
    """Classe un chemin OSM selon les regles d'acces moto / vehicule motorise en Europe."""
    highway = tags.get("highway", "").lower()
    motorcycle = tags.get("motorcycle", "").lower()
    motor_vehicle = tags.get("motor_vehicle", "").lower()
    vehicle = tags.get("vehicle", "").lower()
    access = tags.get("access", "").lower()
    conditional = (
        tags.get("motorcycle:conditional")
        or tags.get("motor_vehicle:conditional")
        or tags.get("vehicle:conditional")
        or tags.get("access:conditional")
    )

    # Priorite hierarchique OSM pour la moto : motorcycle > motor_vehicle > vehicle > access
    effective_moto = motorcycle or motor_vehicle or vehicle or access

    if effective_moto in RESTRICTED_ACCESS_VALUES:
        return "INTERDIT_MOTO"

    if highway in NON_MOTORIZED_HIGHWAYS:
        if motorcycle in ALLOWED_ACCESS_VALUES or motor_vehicle in ALLOWED_ACCESS_VALUES:
            return "CONDITIONNEL" if conditional else "AUTORISE"
        if motorcycle == "permissive" or motor_vehicle == "permissive":
            return "CONDITIONNEL"
        return "INTERDIT_MOTO"

    if conditional or effective_moto == "permissive":
        return "CONDITIONNEL"

    if highway == "track":
        if motorcycle in ALLOWED_ACCESS_VALUES or motor_vehicle in ALLOWED_ACCESS_VALUES or vehicle in ALLOWED_ACCESS_VALUES:
            return "AUTORISE"
        # En Europe (Code forestier / Loi Lalonde), une piste 'track' sans tag explicite doit etre verifiee
        return "A_VERIFIER_PISTE"

    if effective_moto in ALLOWED_ACCESS_VALUES or highway in ("unclassified", "tertiary", "secondary", "residential"):
        return "AUTORISE"

    return "A_VERIFIER_PISTE"


def min_dist_to_geom(pt: TrackPoint, geom: list[dict[str, float]]) -> float:
    """Distance minimale approximee (en metres) entre un point et une geometrie OSM."""
    best = float("inf")
    for node in geom:
        d = haversine_m(pt.lat, pt.lon, node["lat"], node["lon"])
        if d < best:
            best = d
    return best


def audit_track(
    points: list[TrackPoint],
    osm_data: dict[str, Any],
    sample_step: int,
    radius_m: float,
) -> dict[str, Any]:
    """Croise les points du GPX avec les voies et zones protegees OSM (criteres moto)."""
    elements = osm_data.get("elements", [])
    ways = [el for el in elements if el.get("type") == "way" and "highway" in el.get("tags", {}) and "geometry" in el]
    protected = [
        {
            "id": el.get("id"),
            "name": el.get("tags", {}).get("name", "Zone protegee sans nom"),
            "protection_title": el.get("tags", {}).get("protection_title", ""),
        }
        for el in elements
        if el.get("tags", {}).get("boundary") == "protected_area"
    ]

    sampled = points[:: max(1, sample_step)]
    issues: list[dict[str, Any]] = []
    counts = {
        "AUTORISE": 0,
        "A_VERIFIER_PISTE": 0,
        "CONDITIONNEL": 0,
        "INTERDIT_MOTO": 0,
        "HORS_VOIE_OSM": 0,
    }

    for idx, pt in enumerate(sampled):
        best_way = None
        best_dist = float("inf")
        for way in ways:
            d = min_dist_to_geom(pt, way["geometry"])
            if d < best_dist:
                best_dist = d
                best_way = way

        if best_way is None or best_dist > radius_m:
            counts["HORS_VOIE_OSM"] += 1
            continue

        tags = best_way.get("tags", {})
        status = classify_way_moto(tags)
        counts[status] += 1

        if status in ("INTERDIT_MOTO", "CONDITIONNEL", "A_VERIFIER_PISTE"):
            issues.append(
                {
                    "sample_index": idx,
                    "lat": round(pt.lat, 6),
                    "lon": round(pt.lon, 6),
                    "status": status,
                    "osm_way_id": best_way.get("id"),
                    "highway": tags.get("highway"),
                    "motorcycle": tags.get("motorcycle"),
                    "motor_vehicle": tags.get("motor_vehicle"),
                    "vehicle": tags.get("vehicle"),
                    "access": tags.get("access"),
                    "conditional": (
                        tags.get("motorcycle:conditional")
                        or tags.get("motor_vehicle:conditional")
                        or tags.get("access:conditional")
                    ),
                    "tracktype": tags.get("tracktype"),
                    "surface": tags.get("surface"),
                    "smoothness": tags.get("smoothness"),
                    "name": tags.get("name"),
                }
            )

    return {
        "mode": "moto_trail_eu",
        "total_points_gpx": len(points),
        "points_echantillonnes": len(sampled),
        "resume_statuts": counts,
        "zones_protegees_dans_emprise": protected,
        "troncons_a_verifier_ou_interdits": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audite un fichier GPX moto trail contre les regles d'acces motorise OpenStreetMap (Overpass API)."
    )
    parser.add_argument("--gpx", required=True, help="Chemin vers le fichier .gpx a analyser.")
    parser.add_argument("--sample-step", type=int, default=5, help="Pas d'echantillonnage des points GPX (defaut: 5).")
    parser.add_argument("--radius", type=float, default=35.0, help="Rayon max d'appariement OSM en metres (defaut: 35).")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout Overpass en secondes (defaut: 30).")
    args = parser.parse_args()

    try:
        points = parse_gpx(args.gpx)
    except Exception as exc:
        print(f"Erreur lecture GPX: {exc}", file=sys.stderr)
        return 1

    if not points:
        print("Aucun point <trkpt> ou <rtept> trouve dans le fichier GPX.", file=sys.stderr)
        return 1

    pad = 0.002
    lats = [p.lat for p in points]
    lons = [p.lon for p in points]
    bbox = (min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad)

    try:
        osm_data = query_overpass(bbox, timeout=args.timeout)
    except urllib.error.URLError as exc:
        print(f"Erreur reseau Overpass API: {exc}", file=sys.stderr)
        return 2

    report = audit_track(points, osm_data, sample_step=args.sample_step, radius_m=args.radius)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
