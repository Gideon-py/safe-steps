# SafeSteps Bern - PRD

## Original Problem Statement
Full-stack web app for calculating safest school routes for children in Bern, Switzerland. Uses OpenRouteService for routing, OpenStreetMap data via Overpass API for safety scoring, and OTD traffic estimates for real-time traffic awareness.

## Architecture
- **Frontend**: React + Leaflet + TailwindCSS + shadcn/ui
- **Backend**: FastAPI + MongoDB + JWT auth
- **Routing**: ORS Directions API (foot-walking) with 3 alternatives + extra_info (surface, waycategory, waytype)
- **Safety Scoring**: Custom algorithm using Overpass/OSM data with spatial grid indexing + OTD traffic estimates
- **Environment**: OpenWeatherMap (live/mock), Aare guru (live/mock), Flood (mock), OTD Traffic (estimated)

## User Personas
- Parents of school children in Bern needing safe routes
- Teachers/school administrators reviewing routes

## Core Requirements
1. JWT auth (register/login)
2. Interactive Leaflet map with school markers
3. ORS-based walking route calculation (up to 3 alternatives)
4. Safety scoring: 0.35*time + 0.25*osm_risk + 0.25*live_traffic + 0.10*crossings + 0.05*incidents
5. Danger zone visualization (colored fog overlays)
6. Environmental data (weather, Aare, AQI, flood)
7. Pedestrian bridge detection with safety bonus
8. Map legend (permanent, collapsible)
9. Traffic level badges and detour percentages
10. Unified color system (green=safest, amber=balanced, gray=fastest)

## What's Implemented
- JWT auth with register/login/me
- 15 Bern schools with coordinates
- ORS integration with TTL cache (10min), extra_info params, and error handling
- Overpass OSM data with spatial grid indexing (30min cache)
- Safety scoring algorithm v2 with new formula and traffic integration
- OTD client for SOAP/DATEX2 traffic data with time-based fallback
- Pedestrian bridge detection/bonus
- Endpoints: POST /api/route/alternatives, POST /api/route/safest, POST /api/routes/calculate
- Frontend: Map with routes, danger zones, safest badge, risk details
- Legend component (collapsible, showing routes/hazards/markers)
- Traffic level badges (Wenig/Maessiger/Starker Verkehr)
- Detour percentage badges
- 5-field risk breakdown (Strassenrisiko, Live-Verkehr, Querungen, Zeitfaktor, Vorfaelle)
- Schools sorted by distance in dropdown
- Environment widget with live weather data

## Prioritized Backlog
### P0 (Done)
- ORS integration with extra_info
- Safety scoring v2 with new formula
- OTD traffic integration (estimated fallback)
- Master OTD_API_KEY configured
- Map Legend component
- Unified color system
- Traffic and detour badges

### P1 (Next)
- Route comparison side-by-side view
- Saved routes management UI
- Mobile responsive bottom sheet for route panel
- Push notifications for weather warnings

### P2 (Future)
- Live OTD SOAP/DATEX2 integration (when API permissions available)
- School-specific safety zones
- Parent community features
- Mobile app version

## Known Issues
- OTD SOAP API returns 403 (API permissions) - falling back to time-based estimates
- OpenWeatherMap API key sometimes returns 401 - falls back to mock
- Aare.guru DNS resolution fails in container - falls back to mock
