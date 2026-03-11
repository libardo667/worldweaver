#!/usr/bin/env python3
"""
Build a WorldWeaver city pack from OpenStreetMap via the Overpass API.

Usage:
    python scripts/build_city_pack.py --city san_francisco --output data/cities/san_francisco/
    python scripts/build_city_pack.py --city san_francisco --offline  # skip Overpass, use curated data only

What it produces:
    manifest.json          city metadata, bounds, license
    neighborhoods.json     districts with adjacency graph and vibes
    transit_graph.json     stations, lines, stop sequences, connections
    landmarks.json         parks, waterfronts, viewpoints, cultural sites
    street_corridors.json  named corridors with neighborhood mapping and vibe
    inter_city.json        connections to other cities by mode/operator
    weather_config.json    NWS zone + Open-Meteo coordinates for grounding daemon
    transit_config.json    GTFS-rt feed URLs for grounding daemon

The Overpass pull enriches the curated baseline — if OSM data is unavailable,
the curated dataset alone is still a rich, usable pack.

Requirements:
    pip install httpx  (already in worldweaver requirements)

OSM data is ODbL (openstreetmap.org/copyright). See manifest.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _slugify(name: str) -> str:
    """Simple slug: lowercase, spaces → hyphens, drop punctuation."""
    import re

    s = name.lower().strip()
    s = re.sub(r"['\"/]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ---------------------------------------------------------------------------
# Overpass API client
# ---------------------------------------------------------------------------

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# SF bounding box: S, W, N, E
SF_BBOX = "37.7087,-122.5178,37.8324,-122.3571"
# Slightly wider for BART (includes Daly City, Balboa Park)
BART_BBOX = "37.6800,-122.5178,37.8324,-122.3571"


def _overpass_query(query: str, timeout: int = 60) -> dict:
    import httpx

    resp = httpx.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=timeout,
        headers={"User-Agent": "WorldWeaver-CityPackBuilder/1.0 (worldweaver project)"},
    )
    resp.raise_for_status()
    return resp.json()


def _pull_sf_neighborhoods() -> list[dict]:
    """Query OSM for SF neighbourhood nodes and ways."""
    query = f"""
[out:json][timeout:60];
(
  node["place"="neighbourhood"]({SF_BBOX});
  node["place"="quarter"]({SF_BBOX});
  way["place"="neighbourhood"]({SF_BBOX});
);
out center;
"""
    try:
        data = _overpass_query(query)
        results = []
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name") or el.get("tags", {}).get("alt_name")
            if not name:
                continue
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat and lon:
                results.append({"name": name, "lat": float(lat), "lon": float(lon)})
        return results
    except Exception as exc:
        print(f"  [warn] Overpass neighbourhood query failed: {exc}", file=sys.stderr)
        return []


def _pull_bart_stations() -> list[dict]:
    """Query OSM for BART stations."""
    query = f"""
[out:json][timeout:60];
(
  node["railway"="station"]["operator"~"BART",i]({BART_BBOX});
  node["network"~"BART",i]["railway"="station"]({BART_BBOX});
);
out body;
"""
    try:
        data = _overpass_query(query)
        results = []
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name")
            if not name:
                continue
            results.append(
                {
                    "name": name,
                    "lat": float(el["lat"]),
                    "lon": float(el["lon"]),
                    "osm_id": el.get("id"),
                }
            )
        return results
    except Exception as exc:
        print(f"  [warn] Overpass BART query failed: {exc}", file=sys.stderr)
        return []


def _pull_muni_metro_stops() -> list[dict]:
    """Query OSM for key Muni Metro stations (underground + surface stops)."""
    query = f"""
[out:json][timeout:60];
(
  node["railway"="station"]["network"~"Muni|SFMTA",i]({SF_BBOX});
  node["railway"="tram_stop"]["network"~"Muni|SFMTA",i]({SF_BBOX});
);
out body;
"""
    try:
        data = _overpass_query(query)
        results = []
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name")
            if not name:
                continue
            results.append(
                {
                    "name": name,
                    "lat": float(el["lat"]),
                    "lon": float(el["lon"]),
                    "osm_id": el.get("id"),
                    "lines": el.get("tags", {}).get("ref", ""),
                }
            )
        return results
    except Exception as exc:
        print(f"  [warn] Overpass Muni query failed: {exc}", file=sys.stderr)
        return []


def _pull_landmarks() -> list[dict]:
    """Query OSM for parks, viewpoints, cultural sites in SF."""
    query = f"""
[out:json][timeout:90];
(
  way["leisure"="park"]["name"]({SF_BBOX});
  node["tourism"~"attraction|viewpoint|museum|gallery|artwork"]["name"]({SF_BBOX});
  node["amenity"~"theatre|arts_centre|library"]["name"]({SF_BBOX});
  node["natural"="beach"]["name"]({SF_BBOX});
  node["landuse"="recreation_ground"]["name"]({SF_BBOX});
);
out center;
"""
    try:
        data = _overpass_query(query)
        results = []
        seen = set()
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if not lat or not lon:
                continue
            tags = el.get("tags", {})
            ltype = tags.get("leisure") or tags.get("tourism") or tags.get("amenity") or tags.get("natural") or "landmark"
            results.append(
                {
                    "name": name,
                    "type": ltype,
                    "lat": float(lat),
                    "lon": float(lon),
                }
            )
        return results
    except Exception as exc:
        print(f"  [warn] Overpass landmarks query failed: {exc}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Curated baseline — rich, geographically accurate SF data
# These are the authoritative fallback. Overpass data merges into / enriches this.
# ---------------------------------------------------------------------------

CURATED_NEIGHBORHOODS: list[dict] = [
    # Core / Central
    {"name": "The Mission", "lat": 37.7599, "lon": -122.4148, "vibe": "Vibrant Latino heart of SF — murals, taquerias, Mission Dolores, gentrification tension, bike lanes, nightlife on Valencia", "region": "central"},
    {"name": "Castro", "lat": 37.7609, "lon": -122.4350, "vibe": "LGBTQ+ cultural center, Victorians, rainbow crosswalks, Harvey Milk legacy, arts, boutiques, Twin Peaks backdrop", "region": "central"},
    {"name": "Noe Valley", "lat": 37.7502, "lon": -122.4330, "vibe": "Quiet, affluent, stroller-dense, brunch culture, 24th Street commercial strip, valley warmth sheltered from fog", "region": "central"},
    {"name": "Potrero Hill", "lat": 37.7600, "lon": -122.4005, "vibe": "Sunny hill with views, industrial past giving way to tech, good microclimate, dog walkers, converted warehouses", "region": "central"},
    {"name": "Bernal Heights", "lat": 37.7400, "lon": -122.4157, "vibe": "Tight-knit hilltop community, dog park at the summit with panoramic views, artsy, family-oriented, good burritos", "region": "south"},
    {"name": "Glen Park", "lat": 37.7330, "lon": -122.4330, "vibe": "Quiet village feel, canyon park, BART stop, more residential and calm than its neighbors", "region": "south"},
    {"name": "SoMa", "lat": 37.7785, "lon": -122.4056, "vibe": "South of Market — tech offices, SFMOMA, Moscone Center, leather bars, homeless encampments, nightclubs, live-work lofts", "region": "central"},
    {"name": "Tenderloin", "lat": 37.7833, "lon": -122.4133, "vibe": "Dense, difficult, resilient — immigrant restaurants, social services, SROs, Little Saigon, city's hardest edge", "region": "central"},
    {"name": "Civic Center", "lat": 37.7793, "lon": -122.4192, "vibe": "Government buildings, UN Plaza, Davies Symphony Hall, City Hall dome, homeless services, government workers", "region": "central"},
    {"name": "Hayes Valley", "lat": 37.7758, "lon": -122.4244, "vibe": "Boutiques, wine bars, Patricia's Green, opera-crowd cafes, gentrified after freeway removal, design-conscious", "region": "central"},
    # North / Bay
    {"name": "North Beach", "lat": 37.8058, "lon": -122.4103, "vibe": "Beat generation legacy, Italian restaurants, Vesuvio bar, City Lights bookstore, Coit Tower, tourists and old-timers", "region": "north"},
    {"name": "Chinatown", "lat": 37.7941, "lon": -122.4079, "vibe": "Dragon gates, herbalists, dim sum, crowded streets, one of the oldest in the US, Grant Avenue tourism vs Stockton St locals", "region": "north"},
    {"name": "Russian Hill", "lat": 37.8013, "lon": -122.4189, "vibe": "Lombard Street, steep streets, city views, quiet residential, cable car routes, literary history", "region": "north"},
    {"name": "Nob Hill", "lat": 37.7930, "lon": -122.4160, "vibe": "Old money, grand hotels (Fairmont, Mark Hopkins), cable cars, Grace Cathedral, city views, very steep", "region": "north"},
    {"name": "The Tenderloin", "lat": 37.7833, "lon": -122.4133, "vibe": "See Tenderloin", "region": "central"},
    {"name": "Fisherman's Wharf", "lat": 37.8080, "lon": -122.4177, "vibe": "Tourist epicenter — sea lions at Pier 39, crab stands, Alcatraz ferries, Ghirardelli Square, foghorns", "region": "north"},
    {"name": "Marina", "lat": 37.8030, "lon": -122.4370, "vibe": "Young professionals, brunches, Chestnut Street boutiques, Palace of Fine Arts, bay views, earthquake-prone fill", "region": "north"},
    {"name": "Cow Hollow", "lat": 37.7985, "lon": -122.4360, "vibe": "Upscale, Union Street shops and restaurants, between Marina and Pacific Heights, affluent but walkable", "region": "north"},
    {"name": "Pacific Heights", "lat": 37.7925, "lon": -122.4360, "vibe": "Mansions, consulates, city views, very expensive, Lafayette Park, 'Billionaires' Row' on Broadway", "region": "north"},
    {"name": "Japantown", "lat": 37.7853, "lon": -122.4307, "vibe": "Japan Center mall, Peace Pagoda, ramen shops, sake bars, cultural programming, smaller than it once was", "region": "central"},
    {"name": "Western Addition", "lat": 37.7820, "lon": -122.4390, "vibe": "Historically Black neighborhood, Fillmore jazz legacy, painted ladies, mosaic of cultures after urban renewal", "region": "central"},
    {"name": "Fillmore", "lat": 37.7845, "lon": -122.4325, "vibe": "Fillmore Street strip, jazz history, music venues, sushi row, transitional between Japantown and Pacific Heights", "region": "central"},
    {"name": "Haight-Ashbury", "lat": 37.7693, "lon": -122.4469, "vibe": "Summer of Love epicenter, head shops, Victorians, hippie legacy meets current vintage stores, close to GG Park", "region": "west"},
    {"name": "Lower Haight", "lat": 37.7730, "lon": -122.4310, "vibe": "Grittier sibling of Haight, bars and small venues, working class, tattooed locals, less touristy", "region": "central"},
    {"name": "Alamo Square", "lat": 37.7760, "lon": -122.4344, "vibe": "The Painted Ladies, postcard panorama, park with dog walkers and tourists, between Western Addition and Hayes Valley", "region": "central"},
    # West
    {"name": "Inner Sunset", "lat": 37.7626, "lon": -122.4641, "vibe": "Irving Street cafes, foggy mornings, close to GG Park and UCSF, diverse families, N-Judah streetcar", "region": "west"},
    {"name": "Outer Sunset", "lat": 37.7534, "lon": -122.5005, "vibe": "Foggy beach town within a city, surfers at Ocean Beach, Dutch windmills, Vietnamese restaurants, quiet", "region": "west"},
    {"name": "Inner Richmond", "lat": 37.7800, "lon": -122.4678, "vibe": "Clement Street — Asian restaurants, European bakeries, bookshops, fog belt, working class families", "region": "west"},
    {"name": "Outer Richmond", "lat": 37.7776, "lon": -122.5000, "vibe": "Quiet fog, Balboa Street, Lincoln Park, Baker Beach access, more residential and local than Inner Richmond", "region": "west"},
    {"name": "Sunset District", "lat": 37.7534, "lon": -122.4850, "vibe": "Broad umbrella for Outer/Inner Sunset — fog capital of SF, largely residential, N-Judah along Judah St", "region": "west"},
    # South
    {"name": "Excelsior", "lat": 37.7237, "lon": -122.4289, "vibe": "Working-class Latino neighborhood, Mission Street extension, affordable, McLaren Park, diverse immigrants", "region": "south"},
    {"name": "Dogpatch", "lat": 37.7578, "lon": -122.3888, "vibe": "Industrial waterfront being gentrified — craft breweries, design studios, historic buildings, T-Third streetcar", "region": "south"},
    {"name": "Bayview", "lat": 37.7300, "lon": -122.3900, "vibe": "Southeast SF, historically Black, Hunters Point naval shipyard redevelopment, community gardens, food deserts", "region": "south"},
    {"name": "Visitacion Valley", "lat": 37.7137, "lon": -122.4118, "vibe": "Southern tip, working class, diverse Asian and Latino residents, McLaren Park, quiet residential", "region": "south"},
    {"name": "Portola", "lat": 37.7280, "lon": -122.4152, "vibe": "Between Excelsior and Bernal Heights, diverse, Mission Street commercial strip, relatively unknown to outsiders", "region": "south"},
    # Embarcadero / Downtown
    {"name": "Embarcadero", "lat": 37.7955, "lon": -122.3937, "vibe": "Ferry Building, Ferry Plaza Farmers Market, Bay Bridge views, the waterfront promenade, Financial District edge", "region": "downtown"},
    {"name": "Financial District", "lat": 37.7944, "lon": -122.3998, "vibe": "Suits, skyscrapers, lunch hustle, BART stations, transamerica pyramid, quiet on weekends", "region": "downtown"},
    {"name": "Union Square", "lat": 37.7880, "lon": -122.4074, "vibe": "Retail heart — Westfield mall, hotels, theaters, cable car turnaround, Powell BART, very tourist-dense", "region": "downtown"},
]

# BART topology (in-order along shared SF trunk + extensions)
# Line key: YELLOW=Antioch, BLUE=Dublin/Pleasanton, GREEN=Berryessa, RED=Richmond, ORANGE=Berryessa alt
BART_STATIONS: list[dict] = [
    {"name": "Embarcadero", "lat": 37.7929, "lon": -122.3967, "lines": ["red", "yellow", "blue", "green"], "neighborhood": "embarcadero", "notes": "Busiest SF station, Ferry Building, Financial District access"},
    {"name": "Montgomery Street", "lat": 37.7894, "lon": -122.4016, "lines": ["red", "yellow", "blue", "green"], "neighborhood": "financial-district", "notes": "Financial District core, many office workers"},
    {"name": "Powell Street", "lat": 37.7843, "lon": -122.4079, "lines": ["red", "yellow", "blue", "green"], "neighborhood": "union-square", "notes": "Union Square, cable car turnaround, heavy tourist traffic"},
    {"name": "Civic Center", "lat": 37.7793, "lon": -122.4140, "lines": ["red", "yellow", "blue", "green"], "neighborhood": "civic-center", "notes": "City Hall, UN Plaza, Tenderloin edge"},
    {"name": "16th Street Mission", "lat": 37.7651, "lon": -122.4197, "lines": ["red", "yellow", "blue", "green"], "neighborhood": "the-mission", "notes": "Mission core, very active platform, near Valencia corridor"},
    {"name": "24th Street Mission", "lat": 37.7524, "lon": -122.4184, "lines": ["red", "yellow", "blue", "green"], "neighborhood": "the-mission", "notes": "Southern Mission, family neighborhood, good taquerias nearby"},
    {"name": "Glen Park", "lat": 37.7329, "lon": -122.4341, "lines": ["red", "yellow", "blue", "green"], "neighborhood": "glen-park", "notes": "Village stop, canyon park, quieter end of Mission district transit"},
    {"name": "Balboa Park", "lat": 37.7222, "lon": -122.4478, "lines": ["red", "yellow", "blue", "green"], "neighborhood": "excelsior", "notes": "Multi-modal hub — BART, Muni, bus, Excelsior edge"},
    {"name": "Daly City", "lat": 37.7061, "lon": -122.4690, "lines": ["red", "yellow", "blue", "green"], "neighborhood": None, "notes": "First stop outside SF, large parking hub, East Bay transfer"},
]

# Muni Metro lines and key stops (curated — actual stops, not exhaustive)
MUNI_METRO: list[dict] = [
    # N-Judah (most used, Inner Sunset to Caltrain)
    {"name": "N-Judah at Ocean Beach", "lat": 37.7697, "lon": -122.5094, "lines": ["N"], "neighborhood": "outer-sunset", "notes": "Terminal at Great Highway"},
    {"name": "N-Judah at 9th/Irving", "lat": 37.7635, "lon": -122.4677, "lines": ["N"], "neighborhood": "inner-sunset", "notes": "Inner Sunset hub"},
    {"name": "N-Judah at Duboce", "lat": 37.7695, "lon": -122.4334, "lines": ["N"], "neighborhood": "lower-haight", "notes": "Transfers to J-Church, surface tunnel portal"},
    {"name": "Caltrain/4th & King", "lat": 37.7762, "lon": -122.3952, "lines": ["N", "T"], "neighborhood": "soma", "notes": "Transit hub — Caltrain terminus, Muni subway"},
    # J-Church
    {"name": "J-Church at 30th/Church", "lat": 37.7430, "lon": -122.4286, "lines": ["J"], "neighborhood": "noe-valley", "notes": "Noe Valley surface section"},
    {"name": "J-Church at Castro", "lat": 37.7617, "lon": -122.4350, "lines": ["J"], "neighborhood": "castro", "notes": "Castro station underground"},
    # K/T-Third (Bayview waterfront line)
    {"name": "T-Third at Bayview", "lat": 37.7356, "lon": -122.3939, "lines": ["T"], "neighborhood": "bayview", "notes": "Third Street surface — Bayview community hub"},
    {"name": "T-Third at 4th/King", "lat": 37.7762, "lon": -122.3952, "lines": ["T"], "neighborhood": "soma", "notes": "Shared with N terminus"},
    # L-Taraval (West Portal → Ocean Beach)
    {"name": "L-Taraval at West Portal", "lat": 37.7401, "lon": -122.4655, "lines": ["L"], "neighborhood": "west-portal", "notes": "West Portal underground-surface transition"},
    {"name": "L-Taraval at Ocean Beach", "lat": 37.7601, "lon": -122.5094, "lines": ["L"], "neighborhood": "outer-sunset", "notes": "Taraval/Great Highway terminal"},
    # M-Ocean View
    {"name": "West Portal Station", "lat": 37.7401, "lon": -122.4655, "lines": ["J", "K", "L", "M", "S"], "neighborhood": "west-portal", "notes": "Key transfer hub for multiple Muni Metro lines"},
    # Castro Underground Station (serves J, K, L, M, S)
    {"name": "Castro Station", "lat": 37.7625, "lon": -122.4350, "lines": ["J", "K", "L", "M", "S"], "neighborhood": "castro", "notes": "Underground Castro station, all surface lines converge"},
    # Market Street shared trunk
    {"name": "Church Station", "lat": 37.7675, "lon": -122.4289, "lines": ["J", "K", "L", "M", "S"], "neighborhood": "dolores", "notes": "Market & Church, surface-underground transition point"},
    {"name": "Van Ness Station", "lat": 37.7752, "lon": -122.4197, "lines": ["J", "K", "L", "M", "S"], "neighborhood": "civic-center", "notes": "Market & Van Ness underground"},
    {"name": "Civic Center Station", "lat": 37.7793, "lon": -122.4140, "lines": ["J", "K", "L", "M", "S"], "neighborhood": "civic-center", "notes": "Shared with BART Civic Center"},
]

# Key landmarks (parks, waterfronts, cultural sites)
CURATED_LANDMARKS: list[dict] = [
    # Parks / Open Space
    {"name": "Golden Gate Park", "lat": 37.7694, "lon": -122.4862, "type": "park", "neighborhood": "inner-sunset", "description": "1,017-acre urban park — de Young museum, Japanese Tea Garden, Conservatory of Flowers, bison paddock, dutch windmills, Polo Field"},
    {"name": "Dolores Park", "lat": 37.7596, "lon": -122.4269, "type": "park", "neighborhood": "the-mission", "description": "Mission's social hub — picnics, views of downtown, Castro on one side, J-Church streetcar"},
    {"name": "Alamo Square Park", "lat": 37.7762, "lon": -122.4346, "type": "park", "neighborhood": "alamo-square", "description": "The Painted Ladies panorama, steep hill, Victorian row houses, popular with tourists and dog walkers"},
    {"name": "Buena Vista Park", "lat": 37.7700, "lon": -122.4428, "type": "park", "neighborhood": "haight-ashbury", "description": "Forested hilltop park, oldest park in SF, overgrown trails, panoramic views, cruising history"},
    {"name": "McLaren Park", "lat": 37.7205, "lon": -122.4236, "type": "park", "neighborhood": "excelsior", "description": "Second-largest park in SF, overlooked by tourists, community gathering, hiking, disc golf"},
    {"name": "Glen Canyon Park", "lat": 37.7380, "lon": -122.4413, "type": "park", "neighborhood": "glen-park", "description": "Wild canyon in the middle of the city, creek, native plants, neighborhood dogs"},
    {"name": "Bernal Heights Park", "lat": 37.7413, "lon": -122.4155, "type": "park", "neighborhood": "bernal-heights", "description": "Summit park with 360° views, dogs off-leash all over the hill, radio tower, beloved by locals"},
    {"name": "Lafayette Park", "lat": 37.7913, "lon": -122.4339, "type": "park", "neighborhood": "pacific-heights", "description": "Sunken city block park, Pacific Heights living rooms overflow here, dogs, tennis courts"},
    {"name": "Duboce Park", "lat": 37.7693, "lon": -122.4328, "type": "park", "neighborhood": "lower-haight", "description": "Popular dog park, N-Judah streetcar passes alongside, Duboce Triangle neighborhood"},
    # Waterfronts / Beaches
    {"name": "Ocean Beach", "lat": 37.7583, "lon": -122.5100, "type": "beach", "neighborhood": "outer-sunset", "description": "Wild Pacific shore — strong undertow, surfers in wetsuits, bonfires at night, foggy and windswept"},
    {"name": "Baker Beach", "lat": 37.7936, "lon": -122.4836, "type": "beach", "neighborhood": "outer-richmond", "description": "Clothing-optional beach with Golden Gate Bridge backdrop, Marin Headlands view"},
    {"name": "Aquatic Park", "lat": 37.8087, "lon": -122.4237, "type": "waterfront", "neighborhood": "fisherman-s-wharf", "description": "Protected cove, cold-water swimmers, bocce ball, Maritime Museum, cable car terminus nearby"},
    {"name": "Crissy Field", "lat": 37.8038, "lon": -122.4620, "type": "waterfront", "neighborhood": "marina", "description": "Restored tidal marsh and beach along the bay, Golden Gate views, cyclists, dog walkers, kite fliers"},
    {"name": "Embarcadero Waterfront", "lat": 37.7955, "lon": -122.3940, "type": "waterfront", "neighborhood": "embarcadero", "description": "Ferry Building to Bay Bridge — promenade, farmers market, bay views, tourist ferries"},
    # Cultural / Institutional
    {"name": "Ferry Building", "lat": 37.7955, "lon": -122.3937, "type": "market", "neighborhood": "embarcadero", "description": "1898 Beaux-Arts terminal, Saturday farmers market, artisan food vendors, bay views"},
    {"name": "City Hall", "lat": 37.7793, "lon": -122.4193, "type": "civic", "neighborhood": "civic-center", "description": "Gilded dome (taller than DC's Capitol), Harvey Milk was shot here, civic events"},
    {"name": "Coit Tower", "lat": 37.8024, "lon": -122.4058, "type": "monument", "neighborhood": "north-beach", "description": "WPA murals inside, Telegraph Hill views, feral parrots, steps from North Beach"},
    {"name": "Twin Peaks", "lat": 37.7512, "lon": -122.4477, "type": "viewpoint", "neighborhood": "twin-peaks", "description": "Two 922-foot summits, panoramic 360° city view, tourist overlook and local hiking"},
    {"name": "Lands End", "lat": 37.7803, "lon": -122.5134, "type": "coastal", "neighborhood": "outer-richmond", "description": "Rugged coastal bluffs, labyrinth, shipwreck views, Sutro Baths ruins, GGNRA trail"},
    {"name": "Sutro Baths", "lat": 37.7800, "lon": -122.5133, "type": "ruin", "neighborhood": "outer-richmond", "description": "1896 glass-enclosed baths ruins, now a tidal pool at low tide, atmospheric"},
    {"name": "Palace of Fine Arts", "lat": 37.8029, "lon": -122.4484, "type": "monument", "neighborhood": "marina", "description": "Roman rotunda and colonnade reflected in a lagoon, swans, wedding photos, the Marina's jewel"},
    {"name": "de Young Museum", "lat": 37.7714, "lon": -122.4686, "type": "museum", "neighborhood": "inner-sunset", "description": "Fine arts, American art, textiles, tower with free views over GG Park, Golden Gate Bridge"},
    {"name": "California Academy of Sciences", "lat": 37.7699, "lon": -122.4661, "type": "museum", "neighborhood": "inner-sunset", "description": "Natural history — living roof, aquarium, planetarium, rainforest dome, all under one roof in GG Park"},
    {"name": "SFMOMA", "lat": 37.7857, "lon": -122.4006, "type": "museum", "neighborhood": "soma", "description": "Modern art anchor of SoMa, expanded Snøhetta wing, free to walk through ground floor"},
    {"name": "Fillmore Auditorium", "lat": 37.7843, "lon": -122.4326, "type": "venue", "neighborhood": "fillmore", "description": "Legendary music venue, posters are part of the mythology, shaped SF rock history"},
    {"name": "Haight & Ashbury Street", "lat": 37.7693, "lon": -122.4469, "type": "landmark", "neighborhood": "haight-ashbury", "description": "The intersection — street sign tourists, head shops, Summer of Love memorial ground zero"},
    {"name": "Alcatraz Island", "lat": 37.8267, "lon": -122.4230, "type": "historic", "neighborhood": None, "description": "Former federal penitentiary, ferry from Pier 33, bay views, seabirds"},
    {"name": "Fort Mason", "lat": 37.8061, "lon": -122.4319, "type": "cultural", "neighborhood": "marina", "description": "WWII port turned cultural center — SFMOMA rental, farmer markets, theater, Bay views"},
    {"name": "Precita Eyes Murals", "lat": 37.7501, "lon": -122.4138, "type": "art", "neighborhood": "bernal-heights", "description": "Mission mural tradition radiating from Precita Park, community art tours"},
    {"name": "Tartine Manufactory", "lat": 37.7591, "lon": -122.4134, "type": "food", "neighborhood": "the-mission", "description": "The bread line that defines the Mission's food culture — sourdough, pastries, coffee"},
]

# Street corridors with neighborhood mappings and vibes
STREET_CORRIDORS: list[dict] = [
    {"name": "Valencia Street", "neighborhoods": ["the-mission", "noe-valley"], "type": "commercial", "vibe": "The Mission's gentrification spine — restaurants, bookshops, bars, bike lane, taquerias fading to artisanal"},
    {"name": "Mission Street", "neighborhoods": ["the-mission", "excelsior"], "type": "commercial", "vibe": "Working-class corridor, pan-Asian restaurants, dollar stores, Muni 14, the real Mission"},
    {"name": "24th Street", "neighborhoods": ["the-mission", "noe-valley"], "type": "commercial", "vibe": "Southern Mission heart — tortillerias, carnicerias, indie cafes, community murals"},
    {"name": "Market Street", "neighborhoods": ["castro", "civic-center", "soma", "financial-district", "embarcadero"], "type": "boulevard", "vibe": "SF's main artery — Muni Metro, Castro to Ferry Building, bike lanes, Pride parade route"},
    {"name": "Castro Street", "neighborhoods": ["castro"], "type": "commercial", "vibe": "The Castro's vertical strip — bars, bookshops, Castro Theatre marquee, rainbow crosswalks"},
    {"name": "Haight Street", "neighborhoods": ["haight-ashbury", "lower-haight"], "type": "commercial", "vibe": "Head shops to vintage stores — tourist Haight blending into grittier Lower Haight bars"},
    {"name": "Fillmore Street", "neighborhoods": ["fillmore", "pacific-heights", "cow-hollow", "japantown"], "type": "commercial", "vibe": "Jazz history, sushi row, boutiques — ties Pacific Heights to the Fillmore's legacy"},
    {"name": "Divisadero Street", "neighborhoods": ["western-addition", "fillmore", "lower-haight", "haight-ashbury"], "type": "commercial", "vibe": "Gentrifying corridor, brunch spots, barbershops, pan-Asian, NoPa heart"},
    {"name": "Chestnut Street", "neighborhoods": ["marina"], "type": "commercial", "vibe": "Marina's boutique strip — fitness, brunch, weekend shopping, young professionals"},
    {"name": "Union Street", "neighborhoods": ["cow-hollow"], "type": "commercial", "vibe": "Cow Hollow's upscale row — wine bars, antiques, restaurants, Victorians"},
    {"name": "Columbus Avenue", "neighborhoods": ["north-beach", "chinatown"], "type": "boulevard", "vibe": "North Beach's diagonal — Italian restaurants, City Lights, Vesuvio, leads to Chinatown edge"},
    {"name": "Grant Avenue", "neighborhoods": ["chinatown", "north-beach"], "type": "commercial", "vibe": "Chinatown's tourist face — shops, dim sum, dragon gates — shifts to North Beach above Broadway"},
    {"name": "Clement Street", "neighborhoods": ["inner-richmond"], "type": "commercial", "vibe": "Inner Richmond's main street — Asian restaurants, Russian bakeries, produce shops, very local"},
    {"name": "Irving Street", "neighborhoods": ["inner-sunset"], "type": "commercial", "vibe": "Sunset's café row — N-Judah runs alongside, bookstores, tea shops, close to UCSF"},
    {"name": "Judah Street", "neighborhoods": ["inner-sunset", "outer-sunset"], "type": "transit", "vibe": "N-Judah runs down the middle to Ocean Beach — surf shops, family restaurants, fog belt"},
    {"name": "Third Street", "neighborhoods": ["dogpatch", "bayview"], "type": "transit", "vibe": "T-Third streetcar corridor — industrial becoming creative, Dogpatch craft breweries to Bayview"},
    {"name": "Embarcadero", "neighborhoods": ["embarcadero", "financial-district"], "type": "waterfront", "vibe": "Bay-facing boulevard — Ferry Building to AT&T Park, cyclists, joggers, bay air"},
    {"name": "The Great Highway", "neighborhoods": ["outer-sunset"], "type": "coastal", "vibe": "Ocean Beach edge road — closed to cars on weekends, surfers parking, foghorns, windswept"},
    {"name": "19th Avenue", "neighborhoods": ["inner-sunset", "sunset-district", "outer-richmond"], "type": "corridor", "vibe": "City spine through the avenues — mostly cars, connects GG Park to Daly City"},
    {"name": "Potrero Avenue", "neighborhoods": ["potrero-hill", "soma"], "type": "commercial", "vibe": "Hospital row (SF General), auto shops, transitional between SoMa and Potrero Hill"},
]

# Inter-city connections
INTER_CITY: list[dict] = [
    {
        "id": "sf-portland-coast-starlight",
        "from": "san_francisco",
        "to": "portland",
        "mode": "train",
        "operator": "Amtrak Coast Starlight",
        "duration_hours": 17.5,
        "departure_hub": "Emeryville (shuttle from SF BART/ferry)",
        "arrival_hub": "Portland Union Station",
        "notes": "Scenic coastal route, Coast Range and Willamette Valley. Departs once daily.",
    },
    {
        "id": "sf-la-coast-starlight",
        "from": "san_francisco",
        "to": "los_angeles",
        "mode": "train",
        "operator": "Amtrak Coast Starlight",
        "duration_hours": 11.5,
        "departure_hub": "Emeryville (shuttle from SF BART/ferry)",
        "arrival_hub": "Los Angeles Union Station",
        "notes": "Passes through Santa Barbara, San Luis Obispo, the Central Coast.",
    },
    {"id": "sf-la-flight", "from": "san_francisco", "to": "los_angeles", "mode": "flight", "operator": "various (SFO)", "duration_hours": 1.5, "departure_hub": "SFO (BART SFO station)", "arrival_hub": "LAX", "notes": "30+ daily flights. BART from downtown to SFO in ~30 min."},
    {"id": "sf-oakland-bart", "from": "san_francisco", "to": "oakland", "mode": "rail", "operator": "BART", "duration_hours": 0.25, "departure_hub": "Embarcadero/Civic Center BART", "arrival_hub": "12th St / 19th St Oakland", "notes": "Through the Transbay Tube. ~15 min, very frequent."},
    {"id": "sf-berkeley-bart", "from": "san_francisco", "to": "berkeley", "mode": "rail", "operator": "BART", "duration_hours": 0.4, "departure_hub": "Embarcadero BART", "arrival_hub": "Downtown Berkeley BART", "notes": "Red or yellow line, ~25 min."},
    {"id": "sf-sj-caltrain", "from": "san_francisco", "to": "san_jose", "mode": "rail", "operator": "Caltrain", "duration_hours": 1.25, "departure_hub": "4th & King (Caltrain station, Muni N/T)", "arrival_hub": "San José Diridon", "notes": "Peninsula commuter rail, bullet trains ~1h15, locals longer."},
    {"id": "sf-marin-ferry", "from": "san_francisco", "to": "marin_county", "mode": "ferry", "operator": "Golden Gate Ferry", "duration_hours": 0.5, "departure_hub": "Ferry Building", "arrival_hub": "Sausalito or Larkspur", "notes": "Scenic bay crossing with Golden Gate views. Sausalito = bike-friendly."},
    {"id": "sf-amsterdam", "from": "san_francisco", "to": "amsterdam", "mode": "flight", "operator": "KLM / United (SFO)", "duration_hours": 11.5, "departure_hub": "SFO International Terminal", "arrival_hub": "Amsterdam Schiphol", "notes": "Direct nonstop ~11h. Nine-hour time difference."},
]

# Weather + transit config for the grounding daemon
WEATHER_CONFIG: dict = {
    "city": "San Francisco",
    "nws_zone": "CAZ006",
    "nws_county": "SFZ100",
    "nws_point": "37.7749,-122.4194",
    "open_meteo_lat": 37.7749,
    "open_meteo_lon": -122.4194,
    "timezone": "America/Los_Angeles",
    "fog_season": "June through September",
    "microclimate_note": "SF has strong microclimates — Mission is warmer than Sunset by 10-15°F on most days",
}

TRANSIT_CONFIG: dict = {
    "bart": {
        "gtfs_rt_vehicle_positions": "https://api.bart.gov/gtfsrt/tripupdate.aspx",
        "gtfs_rt_service_alerts": "https://api.bart.gov/gtfsrt/alerts.aspx",
        "api_key_required": True,
        "api_key_env": "BART_API_KEY",
        "free_realtime_alt": "https://www.bart.gov/dev/api",
    },
    "muni": {
        "nextbus_api": "https://retro.umoiq.com/service/publicJSONFeed",
        "agency": "sf-muni",
        "note": "NextBus API, no key required",
    },
}


# ---------------------------------------------------------------------------
# Adjacency computation
# ---------------------------------------------------------------------------


def _compute_neighborhood_adjacency(
    neighborhoods: list[dict],
    threshold_km: float = 1.8,
) -> dict[str, list[str]]:
    """
    Build adjacency graph by centroid proximity.
    Two SF neighborhoods are 'adjacent' if centroids are within threshold_km.
    We use 1.8km — generous enough to connect most real SF neighbors.
    """
    adjacency: dict[str, list[str]] = {n["id"]: [] for n in neighborhoods}
    for i, a in enumerate(neighborhoods):
        for j, b in enumerate(neighborhoods):
            if i >= j:
                continue
            dist = _haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            if dist < threshold_km:
                adjacency[a["id"]].append(b["id"])
                adjacency[b["id"]].append(a["id"])
    return adjacency


def _assign_landmark_neighborhoods(landmarks: list[dict], neighborhoods: list[dict]) -> list[dict]:
    """Assign each landmark to its nearest neighborhood by centroid distance."""
    for lm in landmarks:
        if lm.get("neighborhood"):
            continue  # already assigned
        best, best_dist = None, float("inf")
        for n in neighborhoods:
            d = _haversine_km(lm["lat"], lm["lon"], n["lat"], n["lon"])
            if d < best_dist:
                best_dist = d
                best = n["id"]
        lm["neighborhood"] = best
    return landmarks


def _assign_transit_neighborhoods(stations: list[dict], neighborhoods: list[dict]) -> list[dict]:
    """Assign each transit station to its nearest neighborhood."""
    for s in stations:
        if s.get("neighborhood") and any(n["id"] == s["neighborhood"] for n in neighborhoods):
            continue
        best, best_dist = None, float("inf")
        for n in neighborhoods:
            d = _haversine_km(s["lat"], s["lon"], n["lat"], n["lon"])
            if d < best_dist:
                best_dist = d
                best = n["id"]
        s["neighborhood"] = best
    return stations


# ---------------------------------------------------------------------------
# Merge Overpass data into curated baseline
# ---------------------------------------------------------------------------


def _merge_osm_neighborhoods(curated: list[dict], osm: list[dict]) -> list[dict]:
    """Add OSM-discovered neighborhoods not in the curated list (by distance check)."""
    existing_coords = [(n["lat"], n["lon"]) for n in curated]
    added = 0
    for osm_n in osm:
        # Skip if too close to an existing curated entry
        too_close = any(_haversine_km(osm_n["lat"], osm_n["lon"], lat, lon) < 0.5 for lat, lon in existing_coords)
        if not too_close and osm_n["name"]:
            curated.append(
                {
                    "name": osm_n["name"],
                    "lat": osm_n["lat"],
                    "lon": osm_n["lon"],
                    "vibe": "",  # Overpass doesn't give vibes
                    "region": "other",
                    "source": "osm",
                }
            )
            existing_coords.append((osm_n["lat"], osm_n["lon"]))
            added += 1
    if added:
        print(f"  Merged {added} additional neighborhoods from Overpass")
    return curated


def _merge_osm_landmarks(curated: list[dict], osm: list[dict]) -> list[dict]:
    """Add significant OSM landmarks not already in curated list."""
    existing_names = {lm["name"].lower() for lm in curated}
    added = 0
    for osm_lm in osm:
        name = osm_lm.get("name", "")
        if not name or name.lower() in existing_names:
            continue
        # Skip very generic/small things
        if len(name) < 4:
            continue
        curated.append(
            {
                "name": name,
                "lat": osm_lm["lat"],
                "lon": osm_lm["lon"],
                "type": osm_lm.get("type", "landmark"),
                "neighborhood": None,  # will be assigned below
                "description": "",
                "source": "osm",
            }
        )
        existing_names.add(name.lower())
        added += 1
    if added:
        print(f"  Merged {added} additional landmarks from Overpass")
    return curated


def _merge_osm_transit(
    curated_bart: list[dict],
    curated_muni: list[dict],
    osm_bart: list[dict],
    osm_muni: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Enrich curated transit data with OSM coordinates where better."""
    bart_by_name = {s["name"].lower(): s for s in curated_bart}
    for osm_s in osm_bart:
        key = osm_s["name"].lower()
        if key in bart_by_name:
            # Use OSM coordinates if they differ (OSM tends to be precise)
            existing = bart_by_name[key]
            osm_dist = _haversine_km(existing["lat"], existing["lon"], osm_s["lat"], osm_s["lon"])
            if osm_dist > 0.05:  # more than 50m off
                existing["lat"] = osm_s["lat"]
                existing["lon"] = osm_s["lon"]
                existing["osm_id"] = osm_s.get("osm_id")
    return curated_bart, curated_muni


# ---------------------------------------------------------------------------
# Build final pack structures
# ---------------------------------------------------------------------------


def _build_neighborhoods(raw: list[dict]) -> list[dict]:
    """Finalize neighborhood records with IDs and adjacency."""
    # Deduplicate by name
    seen = {}
    for n in raw:
        key = n["name"].lower()
        if key not in seen:
            seen[key] = n
    deduped = list(seen.values())

    # Assign IDs
    for n in deduped:
        n["id"] = _slugify(n["name"])
        n.setdefault("grounding", "grounded_geo")
        n.setdefault("vibe", "")
        n.setdefault("region", "other")

    # Compute adjacency
    adjacency = _compute_neighborhood_adjacency(deduped)
    for n in deduped:
        n["adjacent_to"] = sorted(adjacency[n["id"]])

    return sorted(deduped, key=lambda n: n["name"])


def _build_transit_graph(bart: list[dict], muni: list[dict], neighborhoods: list[dict]) -> dict:
    """Build the transit graph structure."""
    # Assign neighborhoods
    bart = _assign_transit_neighborhoods(bart, neighborhoods)
    muni = _assign_transit_neighborhoods(muni, neighborhoods)

    # Build BART sequential connections (stations are ordered trunk-first)
    bart_connections: dict[str, list[str]] = {}
    bart_ids = [_slugify(f"bart-{s['name']}") for s in bart]
    for i, s in enumerate(bart):
        sid = bart_ids[i]
        conns = []
        if i > 0:
            conns.append(bart_ids[i - 1])
        if i < len(bart) - 1:
            conns.append(bart_ids[i + 1])
        bart_connections[sid] = conns

    bart_stations = []
    for i, s in enumerate(bart):
        sid = bart_ids[i]
        bart_stations.append(
            {
                "id": sid,
                "name": s["name"],
                "grounding": "grounded_geo",
                "system": "BART",
                "lines": s.get("lines", []),
                "lat": s["lat"],
                "lon": s["lon"],
                "neighborhood": s.get("neighborhood"),
                "connects_to": bart_connections[sid],
                "notes": s.get("notes", ""),
            }
        )

    muni_stations = []
    for s in muni:
        muni_stations.append(
            {
                "id": _slugify(f"muni-{s['name']}"),
                "name": s["name"],
                "grounding": "grounded_geo",
                "system": "Muni Metro",
                "lines": s.get("lines", []),
                "lat": s["lat"],
                "lon": s["lon"],
                "neighborhood": s.get("neighborhood"),
                "notes": s.get("notes", ""),
            }
        )

    return {
        "bart": {
            "description": "Bay Area Rapid Transit — heavy rail serving SF and East Bay",
            "fare_zone": "SF is one zone (~$2.50 minimum)",
            "frequency": "Every 15–20 min most hours, 15 min peak",
            "stations": bart_stations,
        },
        "muni_metro": {
            "description": "SF Municipal Railway light rail — underground Market St trunk, surface through neighborhoods",
            "fare": "$3.00 per boarding, free transfers for 90 min",
            "frequency": "Every 10–15 min on major lines",
            "stations": muni_stations,
            "lines": {
                "N": "Judah — Inner Sunset to Caltrain via Market St tunnel",
                "J": "Church — Noe Valley to Embarcadero via Castro",
                "K": "Ingleside — West Portal to Embarcadero",
                "L": "Taraval — Outer Sunset to Embarcadero",
                "M": "Ocean View — Balboa Park to Embarcadero via West Portal",
                "T": "Third — Bayview waterfront to Caltrain/4th & King",
                "S": "Castro Shuttle — Embarcadero to Castro via Market",
            },
        },
    }


def _build_landmarks(raw: list[dict], neighborhoods: list[dict]) -> list[dict]:
    """Finalize landmark records."""
    raw = _assign_landmark_neighborhoods(raw, neighborhoods)
    result = []
    seen = set()
    for lm in raw:
        name = lm.get("name", "")
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(
            {
                "id": _slugify(name),
                "name": name,
                "grounding": "grounded_geo",
                "type": lm.get("type", "landmark"),
                "neighborhood": lm.get("neighborhood"),
                "lat": lm.get("lat"),
                "lon": lm.get("lon"),
                "description": lm.get("description", ""),
            }
        )
    return sorted(result, key=lambda x: x["name"])


def _build_corridors(raw: list[dict]) -> list[dict]:
    result = []
    for c in raw:
        result.append(
            {
                "id": _slugify(c["name"]),
                "name": c["name"],
                "grounding": "grounded_geo",
                "type": c.get("type", "commercial"),
                "neighborhoods": c.get("neighborhoods", []),
                "vibe": c.get("vibe", ""),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_pack(output_dir: Path, offline: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Building San Francisco city pack → {output_dir}")

    # --- 1. Pull Overpass data ---
    osm_neighborhoods: list[dict] = []
    osm_bart: list[dict] = []
    osm_muni: list[dict] = []
    osm_landmarks: list[dict] = []

    if not offline:
        print("Pulling neighborhoods from Overpass API...")
        osm_neighborhoods = _pull_sf_neighborhoods()
        print(f"  Got {len(osm_neighborhoods)} OSM neighbourhood nodes")
        time.sleep(2)  # polite

        print("Pulling BART stations...")
        osm_bart = _pull_bart_stations()
        print(f"  Got {len(osm_bart)} OSM BART stations")
        time.sleep(2)

        print("Pulling Muni Metro stops...")
        osm_muni = _pull_muni_metro_stops()
        print(f"  Got {len(osm_muni)} OSM Muni stops")
        time.sleep(2)

        print("Pulling landmarks...")
        osm_landmarks = _pull_landmarks()
        print(f"  Got {len(osm_landmarks)} OSM landmark elements")
        time.sleep(1)
    else:
        print("Offline mode — using curated baseline only")

    # --- 2. Merge OSM into curated baseline ---
    print("Merging data...")
    all_neighborhoods = _merge_osm_neighborhoods(CURATED_NEIGHBORHOODS[:], osm_neighborhoods)
    all_landmarks = _merge_osm_landmarks(CURATED_LANDMARKS[:], osm_landmarks)
    all_bart, all_muni = _merge_osm_transit(BART_STATIONS[:], MUNI_METRO[:], osm_bart, osm_muni)

    # --- 3. Build final structures ---
    print("Building neighborhood graph...")
    neighborhoods = _build_neighborhoods(all_neighborhoods)
    print(f"  {len(neighborhoods)} neighborhoods with adjacency")

    print("Building transit graph...")
    transit_graph = _build_transit_graph(all_bart, all_muni, neighborhoods)
    bart_count = len(transit_graph["bart"]["stations"])
    muni_count = len(transit_graph["muni_metro"]["stations"])
    print(f"  {bart_count} BART stations, {muni_count} Muni Metro stops")

    print("Building landmarks...")
    landmarks = _build_landmarks(all_landmarks, neighborhoods)
    print(f"  {len(landmarks)} landmarks")

    print("Building street corridors...")
    corridors = _build_corridors(STREET_CORRIDORS)
    print(f"  {len(corridors)} corridors")

    # --- 4. Write files ---
    manifest: dict[str, Any] = {
        "city": "San Francisco",
        "city_id": "san_francisco",
        "version": "1.0.0",
        "built_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "bounds": {"south": 37.7087, "west": -122.5178, "north": 37.8324, "east": -122.3571},
        "source": "openstreetmap.org + curated",
        "license": "ODbL (openstreetmap.org/copyright) for OSM-derived data",
        "counts": {
            "neighborhoods": len(neighborhoods),
            "bart_stations": bart_count,
            "muni_stops": muni_count,
            "landmarks": len(landmarks),
            "corridors": len(corridors),
            "inter_city_routes": len(INTER_CITY),
        },
    }

    files: dict[str, Any] = {
        "manifest.json": manifest,
        "neighborhoods.json": neighborhoods,
        "transit_graph.json": transit_graph,
        "landmarks.json": landmarks,
        "street_corridors.json": corridors,
        "inter_city.json": INTER_CITY,
        "weather_config.json": WEATHER_CONFIG,
        "transit_config.json": TRANSIT_CONFIG,
    }

    for filename, data in files.items():
        path = output_dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        size_kb = path.stat().st_size / 1024
        print(f"  Wrote {filename} ({size_kb:.1f} KB)")

    print(f"\nDone. City pack written to {output_dir}")
    print(f"  Total: {sum((output_dir / f).stat().st_size for f in files) / 1024:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a WorldWeaver city pack from OpenStreetMap")
    parser.add_argument("--city", default="san_francisco", help="City ID (currently only san_francisco)")
    parser.add_argument("--output", default="data/cities/san_francisco", help="Output directory")
    parser.add_argument("--offline", action="store_true", help="Skip Overpass API, use curated data only")
    args = parser.parse_args()

    if args.city != "san_francisco":
        print("Error: only 'san_francisco' is supported in this version", file=sys.stderr)
        sys.exit(1)

    build_pack(Path(args.output), offline=args.offline)


if __name__ == "__main__":
    main()
