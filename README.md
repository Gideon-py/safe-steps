# SafeSteps Bern

Kurze Beschreibung: Web-App die Eltern die sicherste und schnellste 
Schulroute für ihre Kinder in Bern berechnet.

## Tech Stack
- Frontend: React + Leaflet + TailwindCSS + shadcn/ui
- Backend: FastAPI + MongoDB + JWT Auth
- Routing: OpenRouteService (ORS)
- Kartendaten: OpenStreetMap via Overpass API
- Wetter: OpenWeatherMap
- Verkehr: OTD (Open Transport Data)

## Voraussetzungen
- Python 3.11+
- Node.js 18+
- MongoDB (lokal oder Atlas)
- API Keys für: OpenRouteService, OpenWeatherMap, OTD

## Schnellstart mit Docker

**Voraussetzung:** Docker Desktop installiert  
https://www.docker.com/products/docker-desktop

**Schritte:**
```
git clone https://github.com/Gideon-py/safe-steps.git
cd safe-steps
docker-compose up
```

Browser öffnen: http://localhost:3000

**Demo-Login:**  
E-Mail: demo@safesteps.ch  
Passwort: demo1234

## Installation

### Backend
```
cd backend
cp .env.example .env
# .env mit eigenen API Keys befüllen
pip install -r requirements.txt
uvicorn server:app --reload --port 8001
```

### Frontend
```
cd frontend
cp .env.example .env
# REACT_APP_BACKEND_URL=http://localhost:8001 setzen
yarn install
yarn start
```

## Benötigte API Keys
| Key | Wo bekommt man ihn | Kostenlos |
|-----|--------------------|-----------|
| ORS_API_KEY | openrouteservice.org | Ja |
| OPENWEATHERMAP_API_KEY | openweathermap.org | Ja |
| OTD_API_KEY | opentransportdata.swiss | Ja |
| JWT_SECRET | beliebiger langer String | - |

## .env Beispiel Backend (backend/.env.example)
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=safesteps
CORS_ORIGINS=http://localhost:3000
OPENWEATHERMAP_API_KEY=dein_key
ORS_API_KEY=dein_key
OTD_API_KEY=dein_key
JWT_SECRET=dein_geheimer_string
```

## .env Beispiel Frontend (frontend/.env.example)
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

## Demo-Zugang
E-Mail: demo@safesteps.ch  
Passwort: demo1234

## Architektur
- `/api/schools` → Primarschulen & Kindergärten aus OSM (24h Cache)
- `/api/route/alternatives` → bis zu 3 bewertete Routen
- `/api/route/safest` → nur die sicherste Route
- `/api/environment/status` → Wetter, Aare, Luftqualität
