# SafeWay Bern - PRD

## Original Problem Statement
Full-stack web app for calculating safest school routes for children in Bern, Switzerland. Refactored from OSRM to ORS (OpenRouteService) with safety-first routing using OSM data.

## Architecture
- **Frontend**: React + Leaflet + TailwindCSS + shadcn/ui
- **Backend**: FastAPI + MongoDB + JWT auth
- **Routing**: ORS Directions API (foot-walking) with 3 alternatives
- **Safety Scoring**: Custom algorithm using Overpass/OSM data with spatial grid indexing
- **Environment**: OpenWeatherMap (live), Aare guru (live/mock), Flood/Traffic (mock)

## User Personas
- Parents of school children in Bern needing safe routes
- Teachers/school administrators reviewing routes

## Core Requirements
1. JWT auth (register/login)
2. Interactive Leaflet map with school markers
3. ORS-based walking route calculation (up to 3 alternatives)
4. Safety scoring: 0.4*time + 0.3*traffic + 0.2*crossings + 0.1*hotspots
5. Danger zone visualization (red fog overlays)
6. Environmental data (weather, Aare, AQI, flood)
7. Pedestrian bridge detection with safety bonus

## What's Implemented (2026-03-02)
- JWT auth with register/login/me
- 15 Bern schools with coordinates
- ORS integration with TTL cache (10min) and error handling
- Overpass OSM data with spatial grid indexing (30min cache)
- Safety scoring algorithm with detour limits (15% time / 20% distance)
- Pedestrian bridge detection/bonus
- New endpoints: POST /api/route/alternatives, POST /api/route/safest
- Legacy endpoint: POST /api/routes/calculate (backward compat)
- Frontend: Map with routes, danger zones, safest badge, risk details
- Schools sorted by distance in dropdown
- Environment widget with live weather data
- 29 unit tests passing

## Prioritized Backlog
### P0 (Done)
- ORS integration
- Safety scoring
- Danger zones
- Safest route auto-select

### P1 (Next)
- Improve crossing risk normalization
- Add traffic data from real sources
- Route comparison side-by-side view
- Saved routes management UI

### P2 (Future)
- Real-time traffic integration
- School-specific safety zones
- Parent community features
- Push notifications for weather warnings
- Mobile app version
