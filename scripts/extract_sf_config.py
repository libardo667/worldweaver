import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts import build_city_pack

config = {
    "city_id": "san_francisco",
    "city_name": "San Francisco",
    "bboxes": {
        "default": build_city_pack.SF_BBOX,
        "bart": build_city_pack.BART_BBOX
    },
    "transit_systems": [
        {
            "id": "bart",
            "name": "BART",
            "description": "Bay Area Rapid Transit — heavy rail serving SF and East Bay",
            "fare_zone": "SF is one zone (~$2.50 minimum)",
            "frequency": "Every 15–20 min most hours, 15 min peak",
            "stations": build_city_pack.BART_STATIONS,
            "query_template": \"\"\"
[out:json][timeout:60];
(
  node["railway"="station"]["operator"~"BART",i]({bbox});
  node["network"~"BART",i]["railway"="station"]({bbox});
);
out body;
\"\"\",
            "bbox_key": "bart"
        },
        {
            "id": "muni_metro",
            "name": "Muni Metro",
            "description": "SF Municipal Railway light rail — underground Market St trunk, surface through neighborhoods",
            "fare": "$3.00 per boarding, free transfers for 90 min",
            "frequency": "Every 10–15 min on major lines",
            "stations": build_city_pack.MUNI_METRO,
            "lines": {
                "N": "Judah — Inner Sunset to Caltrain via Market St tunnel",
                "J": "Church — Noe Valley to Embarcadero via Castro",
                "K": "Ingleside — West Portal to Embarcadero",
                "L": "Taraval — Outer Sunset to Embarcadero",
                "M": "Ocean View — Balboa Park to Embarcadero via West Portal",
                "T": "Third — Bayview waterfront to Caltrain/4th & King",
                "S": "Castro Shuttle — Embarcadero to Castro via Market"
            },
            "query_template": \"\"\"
[out:json][timeout:60];
(
  node["railway"="station"]["network"~"Muni|SFMTA",i]({bbox});
  node["railway"="tram_stop"]["network"~"Muni|SFMTA",i]({bbox});
);
out body;
\"\"\",
            "bbox_key": "default"
        }
    ],
    "curated_neighborhoods": build_city_pack.CURATED_NEIGHBORHOODS,
    "curated_landmarks": build_city_pack.CURATED_LANDMARKS,
    "street_corridors": build_city_pack.STREET_CORRIDORS,
    "inter_city": build_city_pack.INTER_CITY,
    "weather_config": build_city_pack.WEATHER_CONFIG,
    "transit_config": build_city_pack.TRANSIT_CONFIG
}

with open(r"c:\\Users\\levib\\PythonProjects\\worldweaver\\worldweaver\\scripts\\city_configs\\san_francisco.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("Created san_francisco.json")
