#!/usr/bin/env python3
"""Nearby restaurant search using the public OpenStreetMap Overpass API."""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request

DEFAULT_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
EXCLUDED_AMENITIES = {"cafe", "bar", "pub", "ice_cream"}
CATEGORY_LABELS = {
    "hot_pot": "火锅",
    "barbecue": "烧烤",
    "noodle": "面条",
    "ramen": "面条",
    "japanese": "日料",
    "sushi": "寿司",
    "korean": "韩式料理",
    "burger": "汉堡",
    "pizza": "披萨",
    "chicken": "炸鸡",
    "dumpling": "饺子",
    "chinese": "中餐厅",
}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _category(tags: dict) -> str:
    cuisine = str(tags.get("cuisine") or "").lower().replace("-", "_")
    for key, label in CATEGORY_LABELS.items():
        if key in cuisine:
            return label
    return "快餐" if tags.get("amenity") == "fast_food" else "中餐厅"


def _address(tags: dict) -> str:
    full = tags.get("addr:full")
    if full:
        return str(full)
    parts = [
        tags.get("addr:city"),
        tags.get("addr:district"),
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
    ]
    return " ".join(str(part) for part in parts if part)


def parse_places(document: dict, latitude: float, longitude: float) -> list[dict]:
    places: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    for element in document.get("elements") or []:
        tags = element.get("tags") or {}
        name = str(tags.get("name") or tags.get("name:zh") or "").strip()
        if not name or tags.get("amenity") in EXCLUDED_AMENITIES:
            continue
        center = element.get("center") or element
        try:
            lat = float(center["lat"])
            lon = float(center["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        key = (name, round(lat * 100_000), round(lon * 100_000))
        if key in seen:
            continue
        seen.add(key)
        phone = tags.get("contact:phone") or tags.get("phone") or ""
        places.append(
            {
                "name": name,
                "lat": lat,
                "lon": lon,
                "distance_m": round(haversine_m(latitude, longitude, lat, lon)),
                "address": _address(tags),
                "phone": str(phone),
                "_query": _category(tags),
                "osm_type": element.get("type"),
                "osm_id": element.get("id"),
            }
        )
    return sorted(places, key=lambda place: place["distance_m"])


def search_nearby_food(
    latitude: float,
    longitude: float,
    radius: int = 2500,
    endpoints: tuple[str, ...] = DEFAULT_ENDPOINTS,
) -> list[dict]:
    query = f"""[out:json][timeout:25];
(
  nwr[\"amenity\"~\"^(restaurant|fast_food|food_court)$\"](around:{int(radius)},{latitude:.7f},{longitude:.7f});
);
out center tags;"""
    errors = []
    for endpoint in endpoints:
        request = urllib.request.Request(
            endpoint,
            data=query.encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "User-Agent": "TodooCard-Minis-Android/2.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                document = json.loads(response.read().decode("utf-8"))
            return parse_places(document, latitude, longitude)
        except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as error:
            errors.append(f"{endpoint}: {error}")
    raise RuntimeError("OpenStreetMap restaurant search failed: " + " | ".join(errors))
