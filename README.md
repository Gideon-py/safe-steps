# SafeSteps Bern

Web-App die Eltern die sicherste und schnellste Schulroute für ihre Kinder in Bern berechnet.

## Tech Stack
- Frontend: React + Leaflet + TailwindCSS + shadcn/ui
- Backend: FastAPI + MongoDB + JWT Auth
- Routing: OpenRouteService (ORS)
- Kartendaten: OpenStreetMap via Overpass API
- Wetter: OpenWeatherMap
- Verkehr: OTD (Open Transport Data)

## Installation

**Voraussetzung:** [Docker Desktop](https://www.docker.com/products/docker-desktop) installiert

```
git clone https://github.com/Gideon-py/safe-steps.git
cd safe-steps
docker-compose up
```

Browser öffnen: http://localhost:3000

**Demo-Login:**  
E-Mail: demo@safesteps.ch  
Passwort: demo1234

## Architektur
- `/api/schools` → Primarschulen & Kindergärten aus OSM (24h Cache)
- `/api/route/alternatives` → bis zu 3 bewertete Routen
- `/api/route/safest` → nur die sicherste Route
- `/api/environment/status` → Wetter, Aare, Luftqualität
