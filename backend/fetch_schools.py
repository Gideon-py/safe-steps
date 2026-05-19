import requests, json, sys
from overpass_client import OverpassClient

query = """[out:json][timeout:25];
(
  node["amenity"="kindergarten"](46.92,7.38,46.97,7.49);
  way["amenity"="kindergarten"](46.92,7.38,46.97,7.49);
  node["amenity"="school"]["isced:level"~"1"](46.92,7.38,46.97,7.49);
  way["amenity"="school"]["isced:level"~"1"](46.92,7.38,46.97,7.49);
  node["amenity"="school"]["operator"="Stadt Bern"](46.92,7.38,46.97,7.49);
  way["amenity"="school"]["operator"="Stadt Bern"](46.92,7.38,46.97,7.49);
);
out center;"""

resp = requests.post(
    "https://overpass-api.de/api/interpreter",
    data={"data": query},
    headers={"User-Agent": "curl/7.68.0"},
    timeout=30
)
elements = resp.json().get("elements", [])
schools = OverpassClient._parse_schools(elements)
print(json.dumps(schools))
