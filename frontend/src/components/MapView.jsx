import { useMemo, useCallback } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, useMapEvents, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const BERN_CENTER = [46.9480, 7.4474];

// Colors: safest=green (always primary), others are secondary
const SAFEST_COLOR = "#10B981";
const OTHER_COLOR = "#94A3B8";
const SELECTED_OTHER_COLOR = "#3B82F6";

function createIcon(className, size = [22, 22]) {
  return L.divIcon({
    className: "",
    html: `<div class="${className}"></div>`,
    iconSize: size,
    iconAnchor: [size[0] / 2, size[1] / 2],
  });
}

function MapClickHandler({ onMapClick }) {
  useMapEvents({ click(e) { onMapClick(e.latlng); } });
  return null;
}

function FitBounds({ routes, startPoint, selectedSchool }) {
  const map = useMap();
  useMemo(() => {
    const pts = [];
    routes.forEach((r) => {
      const coords = r.geometry?.coordinates;
      if (coords?.length) {
        coords.forEach((c) => pts.push([c[1], c[0]]));
      }
    });
    if (pts.length > 1) {
      map.fitBounds(L.latLngBounds(pts), { padding: [80, 420, 80, 80], maxZoom: 16 });
    } else if (startPoint && selectedSchool) {
      map.fitBounds(
        [[startPoint.lat, startPoint.lng], [selectedSchool.lat, selectedSchool.lng]],
        { padding: [80, 420, 80, 80], maxZoom: 16 }
      );
    }
  }, [routes, startPoint, selectedSchool, map]);
  return null;
}

/** Convert GeoJSON [lng,lat] → Leaflet [lat,lng] */
function toLeaflet(geojsonCoords) {
  if (!geojsonCoords?.length) return [];
  return geojsonCoords.map((c) => [c[1], c[0]]);
}

export default function MapView({
  schools, startPoint, selectedSchool, routes, selectedRoute,
  onMapClick, onSchoolClick, onRouteClick,
}) {
  const schoolIcon = useMemo(() => createIcon("school-marker"), []);
  const schoolSelectedIcon = useMemo(() => createIcon("school-marker selected", [26, 26]), []);
  const startIcon = useMemo(() => createIcon("start-marker", [26, 26]), []);

  // Collect danger zones from all routes (deduplicated)
  const dangerZones = useMemo(() => {
    const zones = [];
    const seen = new Set();
    routes.forEach((r) => {
      (r.danger_zones || []).forEach((dz) => {
        const key = `${dz.lat.toFixed(4)},${dz.lng.toFixed(4)}`;
        if (!seen.has(key)) {
          seen.add(key);
          zones.push(dz);
        }
      });
    });
    return zones;
  }, [routes]);

  const getRouteStyle = useCallback(
    (route) => {
      const isSafest = route.is_safest;
      const isSelected = route.id === selectedRoute;

      if (isSafest) {
        return {
          color: SAFEST_COLOR,
          weight: isSelected ? 8 : 6,
          opacity: isSelected ? 0.95 : 0.75,
          dashArray: null,
        };
      }
      return {
        color: isSelected ? SELECTED_OTHER_COLOR : OTHER_COLOR,
        weight: isSelected ? 6 : 4,
        opacity: isSelected ? 0.85 : 0.4,
        dashArray: "10, 14",
      };
    },
    [selectedRoute]
  );

  // Sort routes so safest renders on top (last in SVG = on top)
  const sortedRoutes = useMemo(() => {
    const copy = [...routes];
    copy.sort((a, b) => {
      if (a.id === selectedRoute) return 1;
      if (b.id === selectedRoute) return -1;
      if (a.is_safest) return 1;
      if (b.is_safest) return -1;
      return 0;
    });
    return copy;
  }, [routes, selectedRoute]);

  return (
    <div className="absolute inset-0" data-testid="map-container">
      <MapContainer center={BERN_CENTER} zoom={14} className="h-full w-full" zoomControl={true}>
        <TileLayer
          attribution='&copy; <a href="https://carto.com">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        />
        <MapClickHandler onMapClick={onMapClick} />
        <FitBounds routes={routes} startPoint={startPoint} selectedSchool={selectedSchool} />

        {/* Danger zones – red fog circles */}
        {dangerZones.map((dz, i) => (
          <Circle
            key={`dz-${i}`}
            center={[dz.lat, dz.lng]}
            radius={dz.radius || 50}
            pathOptions={{
              fillColor: dz.level === "high" ? "#EF4444" : "#F59E0B",
              fillOpacity: 0.15,
              stroke: false,
            }}
          />
        ))}

        {/* School markers */}
        {schools.map((s) => (
          <Marker
            key={s.id}
            position={[s.lat, s.lng]}
            icon={selectedSchool?.id === s.id ? schoolSelectedIcon : schoolIcon}
            eventHandlers={{ click: () => onSchoolClick(s) }}
          >
            <Popup>
              <div className="p-3 min-w-[180px]">
                <p className="font-bold text-sm text-slate-800 mb-1">{s.name}</p>
                <p className="text-xs text-slate-500">{s.type}</p>
                <p className="text-xs text-slate-500 mt-1">{s.address}</p>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Start point marker */}
        {startPoint && (
          <Marker position={[startPoint.lat, startPoint.lng]} icon={startIcon}>
            <Popup>
              <div className="p-3">
                <p className="font-bold text-sm text-slate-800">Startpunkt</p>
                <p className="text-xs text-slate-500 mt-1">
                  {startPoint.lat.toFixed(4)}, {startPoint.lng.toFixed(4)}
                </p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Route polylines */}
        {sortedRoutes.map((r) => (
          <Polyline
            key={r.id}
            positions={toLeaflet(r.geometry?.coordinates)}
            pathOptions={getRouteStyle(r)}
            eventHandlers={{
              click: () => onRouteClick?.(r.id),
            }}
          />
        ))}
      </MapContainer>
    </div>
  );
}
