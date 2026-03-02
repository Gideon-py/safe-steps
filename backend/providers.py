import httpx
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def _owm_key():
    return os.environ.get('OPENWEATHERMAP_API_KEY', '')


class WeatherProvider:
    """Live weather data via OpenWeatherMap API. Falls back to mock."""

    async def get_data(self, lat: float, lng: float) -> dict:
        key = _owm_key()
        if key:
            try:
                url = "https://api.openweathermap.org/data/2.5/weather"
                params = {
                    "lat": lat, "lon": lng,
                    "appid": key,
                    "units": "metric", "lang": "de"
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        d = resp.json()
                        return {
                            "source": "live",
                            "provider": "OpenWeatherMap",
                            "data": {
                                "temp": d["main"]["temp"],
                                "feels_like": d["main"]["feels_like"],
                                "humidity": d["main"]["humidity"],
                                "description": d["weather"][0]["description"],
                                "icon": d["weather"][0]["icon"],
                                "wind_speed": d["wind"]["speed"],
                                "rain_mm": d.get("rain", {}).get("1h", 0),
                                "clouds": d["clouds"]["all"],
                                "visibility": d.get("visibility", 10000),
                            },
                        }
            except Exception as e:
                logger.warning(f"Weather API error: {e}")
        return self._mock()

    def _mock(self):
        return {
            "source": "demo",
            "provider": "Mock",
            "data": {
                "temp": 14.5, "feels_like": 12.8, "humidity": 72,
                "description": "Leicht bewoelkt", "icon": "02d",
                "wind_speed": 8.5, "rain_mm": 0, "clouds": 40, "visibility": 10000,
            },
        }


class AirQualityProvider:
    """Live air quality via OpenWeatherMap Air Pollution API."""

    async def get_data(self, lat: float, lng: float) -> dict:
        key = _owm_key()
        if key:
            try:
                url = "http://api.openweathermap.org/data/2.5/air_pollution"
                params = {"lat": lat, "lon": lng, "appid": key}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        d = resp.json()
                        item = d["list"][0]
                        aqi = item["main"]["aqi"]
                        labels = {1: "Gut", 2: "Akzeptabel", 3: "Maessig", 4: "Schlecht", 5: "Sehr schlecht"}
                        return {
                            "source": "live",
                            "provider": "OpenWeatherMap",
                            "data": {
                                "aqi": aqi,
                                "aqi_label": labels.get(aqi, "Unbekannt"),
                                "pm25": item["components"].get("pm2_5", 0),
                                "pm10": item["components"].get("pm10", 0),
                                "no2": item["components"].get("no2", 0),
                                "o3": item["components"].get("o3", 0),
                            },
                        }
            except Exception as e:
                logger.warning(f"Air quality API error: {e}")
        return self._mock()

    def _mock(self):
        return {
            "source": "demo", "provider": "Mock",
            "data": {"aqi": 2, "aqi_label": "Akzeptabel", "pm25": 12.5, "pm10": 22.3, "no2": 18.7, "o3": 45.2},
        }


class AareProvider:
    """Aare river data via aare.guru API. Falls back to mock."""

    async def get_data(self) -> dict:
        try:
            url = "https://aareguru.ch/v2018/current?city=bern&app=SafeWayBern&version=1.0"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    d = resp.json()
                    aare = d.get("aare", d)
                    temp = aare.get("temperature", aare.get("temperature_prec", 15))
                    flow = aare.get("flow", 150)
                    return {
                        "source": "live",
                        "provider": "aare.guru",
                        "data": {
                            "temperature": temp,
                            "temperature_text": aare.get("temperature_text", f"{temp} C"),
                            "flow": flow,
                            "flow_text": aare.get("flow_text", f"{flow} m3/s"),
                            "danger_level": self._danger(temp, flow),
                            "danger_text": self._danger_text(temp, flow),
                        },
                    }
        except Exception as e:
            logger.warning(f"Aare API error: {e}")
        return self._mock()

    def _danger(self, temp, flow):
        if flow > 400 or temp < 5:
            return "high"
        if flow > 250 or temp < 10:
            return "medium"
        return "low"

    def _danger_text(self, temp, flow):
        if flow > 400:
            return "Hohe Stroemung - Vorsicht am Ufer!"
        if temp < 10:
            return "Kalte Wassertemperatur"
        return "Normale Bedingungen"

    def _mock(self):
        return {
            "source": "demo", "provider": "Mock",
            "data": {
                "temperature": 16.2, "temperature_text": "Angenehm kuehl",
                "flow": 165, "flow_text": "Normalabfluss",
                "danger_level": "low", "danger_text": "Normale Bedingungen",
            },
        }


class FloodProvider:
    """Flood warnings. Mock data (realistic for Bern region)."""

    async def get_data(self) -> dict:
        return {
            "source": "demo",
            "provider": "Mock (BAFU Naturgefahren)",
            "data": {
                "warning_active": False,
                "warning_level": 1,
                "warning_text": "Keine aktuelle Warnung",
                "regions": [
                    {"name": "Aare Bern", "level": 1, "status": "normal"},
                    {"name": "Guerbe", "level": 1, "status": "normal"},
                ],
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
        }


class TrafficProvider:
    """Traffic patterns. Mock data with time-based intensity."""

    def get_data(self, departure_time: str = "08:00") -> dict:
        try:
            hour = int(departure_time.split(":")[0])
        except Exception:
            hour = 8

        pattern = {
            6: 30, 7: 65, 8: 85, 9: 60, 10: 35, 11: 30, 12: 45,
            13: 40, 14: 35, 15: 50, 16: 75, 17: 90, 18: 70, 19: 45, 20: 25,
        }
        intensity = pattern.get(hour, 20)
        level = "low" if intensity < 40 else ("medium" if intensity < 70 else "high")

        return {
            "source": "demo",
            "provider": "Mock (Zeitbasiert)",
            "data": {
                "intensity": intensity,
                "level": level,
                "description": f"{'Geringes' if level == 'low' else 'Maessiges' if level == 'medium' else 'Hohes'} Verkehrsaufkommen",
                "rush_hour": hour in [7, 8, 9, 16, 17, 18],
                "hot_zones": [
                    {"name": "Bahnhof Bern", "lat": 46.9490, "lng": 7.4390, "intensity": min(100, intensity + 15)},
                    {"name": "Wankdorfplatz", "lat": 46.9630, "lng": 7.4670, "intensity": min(100, intensity + 10)},
                    {"name": "Helvetiaplatz", "lat": 46.9430, "lng": 7.4470, "intensity": min(100, intensity + 5)},
                ],
            },
        }
