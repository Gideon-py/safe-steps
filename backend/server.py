from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import jwt
import bcrypt
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Any

from providers import (
    WeatherProvider, AirQualityProvider, AareProvider,
    FloodProvider, TrafficProvider,
)
from ors_client import ORSClient, ORSError
from overpass_client import OverpassClient
from otd_client import OTDClient
from route_safety_service import (
    score_all_routes, score_bridge_route, find_bridges_in_corridor, haversine,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT
JWT_SECRET = os.environ.get('JWT_SECRET', 'safesteps_default_secret')
JWT_ALG = "HS256"
security = HTTPBearer()

# Providers
weather_prov = WeatherProvider()
air_prov = AirQualityProvider()
aare_prov = AareProvider()
flood_prov = FloodProvider()
traffic_prov = TrafficProvider()

# ORS + Overpass + OTD Traffic
ors = ORSClient()
overpass = OverpassClient()
otd = OTDClient()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    for attempt in range(10):
        try:
            existing = await db.users.find_one({"email": "demo@safesteps.ch"})
            if not existing:
                uid = str(uuid.uuid4())
                await db.users.insert_one({
                    "id": uid,
                    "email": "demo@safesteps.ch",
                    "name": "Demo User",
                    "password_hash": hash_pw("demo1234"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("Demo user created")
            break
        except Exception as e:
            logger.warning(f"Demo user attempt {attempt+1} failed: {e}")
            await asyncio.sleep(3)
    else:
        logger.error("Could not create demo user after all retries")
    yield


app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")

# ──────────── Models ────────────

class UserRegister(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class RouteInput(BaseModel):
    start: Dict[str, float]  # {"lat": ..., "lng": ...}
    dest: Dict[str, float]

class RouteBySchool(BaseModel):
    start_lat: float
    start_lng: float
    school_id: str
    departure_time: str = "07:30"

class SaveRouteRequest(BaseModel):
    route_name: str
    route_data: Dict[str, Any]

# ──────────── Auth helpers ────────────

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_pw(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())

def create_token(uid: str, email: str) -> str:
    return jwt.encode(
        {"user_id": uid, "email": email, "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        JWT_SECRET, algorithm=JWT_ALG,
    )

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(401, "User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

# ──────────── Auth routes ────────────

@api_router.post("/auth/register")
async def register(data: UserRegister):
    if await db.users.find_one({"email": data.email}):
        raise HTTPException(400, "Email already registered")
    uid = str(uuid.uuid4())
    doc = {
        "id": uid, "email": data.email, "name": data.name,
        "password_hash": hash_pw(data.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    token = create_token(uid, data.email)
    return {"token": token, "user": {"id": uid, "email": data.email, "name": data.name}}

@api_router.post("/auth/login")
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or not verify_pw(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user["id"], user["email"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}

@api_router.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"]}

# ──────────── Schools ────────────

@api_router.get("/schools")
async def get_schools():
    return await overpass.get_schools()

# ──────────── Environment ────────────

@api_router.get("/environment/status")
async def get_environment_status():
    lat, lng = 46.9480, 7.4474
    weather = await weather_prov.get_data(lat, lng)
    air = await air_prov.get_data(lat, lng)
    aare = await aare_prov.get_data()
    flood = await flood_prov.get_data()

    warnings = []
    level = "ok"
    wd = weather.get("data", {})
    if wd.get("rain_mm", 0) > 5:
        warnings.append("Starker Regen erwartet")
        level = "warning"
    if wd.get("temp", 20) > 33:
        warnings.append("Hitzewarnung aktiv")
        level = "warning"
    if wd.get("temp", 20) < -5:
        warnings.append("Frost/Glaette moeglich")
        level = "warning"
    if flood.get("data", {}).get("warning_active"):
        warnings.append(flood["data"].get("warning_text", "Hochwasserwarnung"))
        level = "danger"
    if air.get("data", {}).get("aqi", 1) >= 4:
        warnings.append("Schlechte Luftqualitaet")
        level = "warning"

    return {
        "weather": weather, "air_quality": air, "aare": aare, "flood": flood,
        "warnings": warnings, "warning_level": level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# ──────────── Core routing pipeline ────────────

async def _compute_routes(start_lat, start_lng, end_lat, end_lng):
    """Shared pipeline: ORS → Overpass → OTD Traffic → Safety scoring → bridge bonus."""
    # 1. Get ORS alternatives
    ors_data = await ors.get_alternatives(start_lat, start_lng, end_lat, end_lng)
    features = ors_data.get("features", [])
    if not features:
        raise HTTPException(404, "No routes found")

    # 2. Get OSM features along routes (all coords merged)
    all_coords = []
    for f in features:
        all_coords.extend(f["geometry"]["coordinates"])
    osm = await overpass.get_features(all_coords)

    # 3. Fetch live traffic data for each route in parallel
    traffic_data_list = []
    incidents_list = []
    for f in features:
        coords = f["geometry"]["coordinates"]
        traffic = await otd.get_traffic_near_route(coords)
        incidents = await otd.get_incidents_near_route(coords)
        traffic_data_list.append(traffic)
        incidents_list.append(incidents)

    # 4. Score all routes with traffic data
    scored = score_all_routes(features, osm, traffic_data_list, incidents_list)
    if not scored:
        raise HTTPException(404, "All routes exceed detour limits or have excessive traffic")

    # 5. Check for pedestrian bridges → bonus route
    min_dur = min(r["duration_s"] for r in scored)
    min_dist = min(r["distance_m"] for r in scored)
    primary_coords = features[0]["geometry"]["coordinates"]
    bridges = find_bridges_in_corridor(primary_coords, osm, corridor_m=100)

    # Use first route's traffic data for bridge route
    bridge_traffic = traffic_data_list[0] if traffic_data_list else None
    bridge_incidents = incidents_list[0] if incidents_list else None

    for blat, blng in bridges[:1]:
        try:
            via_data = await ors.get_route_via(
                start_lat, start_lng, blat, blng, end_lat, end_lng
            )
            via_features = via_data.get("features", [])
            if via_features:
                br_result = score_bridge_route(
                    via_features[0], osm, min_dur, min_dist,
                    traffic_data=bridge_traffic,
                    incidents=bridge_incidents,
                )
                if br_result:
                    scored.append(br_result)
        except Exception as e:
            logger.warning("Bridge route failed: %s", e)

    # Re-sort and re-flag safest
    scored.sort(key=lambda r: r["total_cost"])
    for r in scored:
        r["is_safest"] = False
    if scored:
        scored[0]["is_safest"] = True

    # Limit to 3 routes max
    return scored[:3]


# ──────────── Route endpoints ────────────

@api_router.post("/route/alternatives")
async def route_alternatives(data: RouteInput):
    """Return up to 3 scored route alternatives."""
    try:
        routes = await _compute_routes(
            data.start["lat"], data.start["lng"],
            data.dest["lat"], data.dest["lng"],
        )
        return {"routes": routes}
    except ORSError as e:
        raise HTTPException(e.status, e.message)


@api_router.post("/route/safest")
async def route_safest(data: RouteInput):
    """Return only the safest route."""
    try:
        routes = await _compute_routes(
            data.start["lat"], data.start["lng"],
            data.dest["lat"], data.dest["lng"],
        )
        safest = next((r for r in routes if r["is_safest"]), routes[0])
        return safest
    except ORSError as e:
        raise HTTPException(e.status, e.message)


@api_router.post("/routes/calculate")
async def calculate_routes(data: RouteBySchool):
    """Legacy endpoint: resolve school_id → coordinates, then compute."""
    schools = await overpass.get_schools()
    school = next((s for s in schools if s["id"] == data.school_id), None)
    if not school:
        raise HTTPException(404, "School not found")

    try:
        routes = await _compute_routes(
            data.start_lat, data.start_lng, school["lat"], school["lng"]
        )
    except ORSError as e:
        raise HTTPException(e.status, e.message)

    # Enrich with legacy fields for backward compat
    dep_time = data.departure_time
    for r in routes:
        dur_min = round(r["duration_s"] / 60)
        try:
            eta = (datetime.strptime(dep_time, "%H:%M") + timedelta(minutes=dur_min)).strftime("%H:%M")
        except Exception:
            eta = "--:--"
        r["duration_minutes"] = dur_min
        r["eta"] = eta
        r["distance_meters"] = r["distance_m"]

    # Determine traffic source
    traffic_source = "Zeitbasiert (geschaetzt)"
    for r in routes:
        if r.get("traffic_level") and r["traffic_level"] != "unknown":
            # Check if any route has live OTD data
            traffic_source = "OTD (geschaetzt)"
            break

    return {
        "routes": routes,
        "school": school,
        "start": {"lat": data.start_lat, "lng": data.start_lng},
        "routing_source": "ors_live",
        "data_sources": {
            "routing": "ORS",
            "safety": "Overpass+OSM",
            "traffic": traffic_source,
        },
    }

# ──────────── Saved routes ────────────

@api_router.post("/routes/save")
async def save_route(data: SaveRouteRequest, user=Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()), "user_id": user["id"],
        "route_name": data.route_name, "route_data": data.route_data,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.saved_routes.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

@api_router.get("/routes/saved")
async def get_saved_routes(user=Depends(get_current_user)):
    return await db.saved_routes.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)

@api_router.delete("/routes/saved/{route_id}")
async def delete_saved_route(route_id: str, user=Depends(get_current_user)):
    result = await db.saved_routes.delete_one({"id": route_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Route not found")
    return {"deleted": True}

# ──────────── App setup ────────────

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

