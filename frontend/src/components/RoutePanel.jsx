import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  MapPin, School, Clock, Navigation, AlertTriangle, ChevronDown, ChevronUp,
  Bookmark, Shield, Zap, Scale, Footprints, Car, TriangleAlert, Search,
} from "lucide-react";
import { useState, useMemo } from "react";

function haversineJS(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Route type colors
const ROUTE_COLORS = {
  safest: "#10B981",
  balanced: "#F59E0B",
  fastest: "#64748B",
};

function ScoreBadge({ score }) {
  const bg = score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className={`safety-badge ${bg} text-white`} data-testid="safety-score-badge">
      {score}%
    </div>
  );
}

function TrafficBadge({ level }) {
  if (!level || level === "unknown") return null;
  const styles = {
    low: "bg-emerald-50 text-emerald-700",
    medium: "bg-amber-50 text-amber-700",
    high: "bg-red-50 text-red-700",
  };
  const labels = {
    low: "Wenig Verkehr",
    medium: "Maessiger Verkehr",
    high: "Starker Verkehr",
  };
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${styles[level] || styles.medium}`}
          data-testid="traffic-badge">
      <Car className="h-3 w-3" />
      {labels[level] || level}
    </span>
  );
}

function getRouteType(route, routes) {
  if (route.is_safest) return "safest";
  if (route.via_bridge) return "balanced";
  const sortedByDuration = [...routes].sort((a, b) => (a.duration_s || 0) - (b.duration_s || 0));
  if (sortedByDuration.length > 0 && route.id === sortedByDuration[0].id) return "fastest";
  return "balanced";
}

function getRouteLabel(route, routes) {
  if (route.is_safest) return "Sicherste Route";
  if (route.via_bridge) return "Via Bruecke";
  const type = getRouteType(route, routes);
  if (type === "fastest") return "Schnellste Route";
  return "Alternative";
}

function getRouteIcon(route, routes) {
  if (route.is_safest) return <Shield className="h-4 w-4 text-emerald-500" />;
  if (route.via_bridge) return <Footprints className="h-4 w-4 text-cyan-500" />;
  const type = getRouteType(route, routes);
  if (type === "fastest") return <Zap className="h-4 w-4 text-slate-500" />;
  return <Scale className="h-4 w-4 text-amber-500" />;
}

function RouteCard({ route, isSelected, onSelect, onSave, allRoutes }) {
  const [expanded, setExpanded] = useState(false);
  const routeType = getRouteType(route, allRoutes);
  const isSafest = route.is_safest;

  const durationMin = route.duration_minutes ?? Math.round((route.duration_s || 0) / 60);
  const distanceM = route.distance_meters ?? route.distance_m ?? 0;
  const detourPct = route.detour_pct || 0;

  const indicatorColor = ROUTE_COLORS[routeType] || ROUTE_COLORS.balanced;

  return (
    <div
      className={`rounded-xl border-2 p-4 cursor-pointer transition-all duration-200 relative ${
        isSelected
          ? "border-primary bg-primary/5 shadow-md"
          : "border-transparent bg-white hover:border-slate-200 hover:shadow-sm"
      }`}
      onClick={() => onSelect(route.id)}
      data-testid={`route-card-${route.id}`}
    >
      {/* Safest badge */}
      {isSafest && (
        <div className="absolute -top-2.5 right-3 z-10" data-testid="safest-route-badge">
          <Badge className="bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 shadow-sm">
            <Shield className="h-3 w-3 mr-1" /> Sicherste Route
          </Badge>
        </div>
      )}

      <div className="flex items-start gap-3">
        <div
          className="route-indicator"
          style={{ background: indicatorColor }}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              {getRouteIcon(route, allRoutes)}
              <span className="font-semibold text-sm text-foreground">
                {getRouteLabel(route, allRoutes)}
              </span>
            </div>
            <ScoreBadge score={route.safety_score} />
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-2 flex-wrap">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" /> {durationMin} Min.
            </span>
            <span className="flex items-center gap-1">
              <Navigation className="h-3 w-3" /> {(distanceM / 1000).toFixed(1)} km
            </span>
            {route.eta && <span className="font-medium text-foreground">ETA {route.eta}</span>}
          </div>

          {/* Detour + Traffic info */}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {detourPct > 0 && (
              <span className="text-[10px] text-muted-foreground bg-slate-100 px-1.5 py-0.5 rounded" data-testid="detour-badge">
                +{detourPct}% Umweg
              </span>
            )}
            <TrafficBadge level={route.traffic_level} />
          </div>

          {/* Risk breakdown */}
          {route.risk_details && (
            <div className="mt-3">
              <button
                className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                data-testid={`risk-toggle-${route.id}`}
              >
                <AlertTriangle className="h-3 w-3" />
                Risiko-Details
                {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
              {expanded && (
                <div className="mt-2 space-y-1.5 slide-up-enter">
                  <RiskBar label="Strassenrisiko" value={route.risk_details.osm_risk ?? route.risk_details.traffic_risk} color="osm" />
                  <RiskBar label="Live-Verkehr" value={route.risk_details.traffic_risk} color="traffic" />
                  <RiskBar label="Querungen" value={route.risk_details.crossing_risk} color="crossing" />
                  <RiskBar label="Zeitfaktor" value={route.risk_details.time_penalty} color="time" />
                  <RiskBar label="Vorfaelle" value={route.risk_details.incident_risk ?? 0} color="incident" />
                </div>
              )}
            </div>
          )}

          {/* Save button */}
          {isSelected && (
            <Button
              variant="ghost" size="sm" className="mt-2 h-7 text-xs"
              onClick={(e) => { e.stopPropagation(); onSave(route); }}
              data-testid={`save-route-${route.id}`}
            >
              <Bookmark className="h-3 w-3 mr-1" /> Speichern
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function RiskBar({ label, value, color = "default" }) {
  const barColor = value >= 60 ? "bg-red-400" : value >= 30 ? "bg-amber-400" : "bg-emerald-400";
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-muted-foreground w-24 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="text-[10px] font-mono text-muted-foreground w-7 text-right">{value}</span>
    </div>
  );
}

export default function RoutePanel({
  startPoint, selectedSchool, schools, departureTime, onDepartureTimeChange,
  onSchoolSelect, onCalculate, calculating, routes, selectedRoute, onSelectRoute,
  onSaveRoute, dataSources, routingSource, onStartPointChange,
}) {
  const [addressQuery, setAddressQuery] = useState("");
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeError, setGeocodeError] = useState("");

  const handleGeocode = async (e) => {
    e.preventDefault();
    if (!addressQuery.trim()) return;
    setGeocoding(true);
    setGeocodeError("");
    try {
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(addressQuery)}&format=json&limit=1&countrycodes=ch`;
      const resp = await fetch(url, { headers: { "Accept-Language": "de" } });
      const data = await resp.json();
      if (!data.length) {
        setGeocodeError("Adresse nicht gefunden");
        return;
      }
      onStartPointChange({ lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) });
      setGeocodeError("");
    } catch {
      setGeocodeError("Geocoding fehlgeschlagen");
    } finally {
      setGeocoding(false);
    }
  };

  // Sort schools by distance to startPoint
  const sortedSchools = useMemo(() => {
    if (!startPoint || !(schools || []).length) return schools || [];
    return [...(schools || [])].sort((a, b) => {
      const dA = haversineJS(startPoint.lat, startPoint.lng, a.lat, a.lng);
      const dB = haversineJS(startPoint.lat, startPoint.lng, b.lat, b.lng);
      return dA - dB;
    });
  }, [schools, startPoint]);

  return (
    <ScrollArea className="h-full">
      <div className="glass-panel rounded-2xl p-5 space-y-5" data-testid="route-panel">
        {/* Input section */}
        <div className="space-y-4">
          <h2 className="font-bold font-['Barlow'] text-lg text-foreground tracking-tight">Route planen</h2>

          {/* Start point – address search */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Startpunkt</Label>
            <form onSubmit={handleGeocode} className="flex gap-2">
              <Input
                value={addressQuery}
                onChange={(e) => setAddressQuery(e.target.value)}
                placeholder="Ihre Adresse in Bern eingeben..."
                data-testid="address-search-input"
              />
              <Button
                type="submit"
                size="icon"
                disabled={!addressQuery.trim() || geocoding}
                data-testid="address-search-btn"
              >
                {geocoding
                  ? <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                  : <Search className="h-4 w-4" />}
              </Button>
            </form>
            {startPoint && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <MapPin className="h-3 w-3 text-emerald-500 flex-shrink-0" />
                <span data-testid="start-point-display">
                  {startPoint.lat.toFixed(5)}, {startPoint.lng.toFixed(5)}
                </span>
              </div>
            )}
            {geocodeError && (
              <p className="text-xs text-red-500">{geocodeError}</p>
            )}
          </div>

          {/* School select */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Schule</Label>
            <Select
              value={selectedSchool?.id || ""}
              onValueChange={(val) => {
                const s = schools.find((sc) => sc.id === val);
                if (s) onSchoolSelect(s);
              }}
            >
              <SelectTrigger data-testid="school-select">
                <SelectValue placeholder="Schule waehlen..." />
              </SelectTrigger>
              <SelectContent>
                {sortedSchools.map((s) => {
                  const dist = startPoint
                    ? (haversineJS(startPoint.lat, startPoint.lng, s.lat, s.lng) / 1000).toFixed(1)
                    : null;
                  return (
                    <SelectItem key={s.id} value={s.id}>
                      <div className="flex items-center gap-2 w-full">
                        <School className="h-3.5 w-3.5 text-blue-500 flex-shrink-0" />
                        <span className="truncate">{s.name}</span>
                        {dist && (
                          <span className="text-[10px] text-muted-foreground ml-auto">{dist} km</span>
                        )}
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>

          {/* Departure time */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Abgangszeit</Label>
            <Input
              type="time"
              value={departureTime}
              onChange={(e) => onDepartureTimeChange(e.target.value)}
              data-testid="departure-time-input"
            />
          </div>

          <Button
            className="w-full"
            onClick={onCalculate}
            disabled={!startPoint || !selectedSchool || calculating}
            data-testid="calculate-routes-btn"
          >
            {calculating ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                Berechne...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Navigation className="h-4 w-4" /> Route berechnen
              </span>
            )}
          </Button>
        </div>

        {/* Routes */}
        {routes.length > 0 && (
          <>
            <Separator />
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-bold font-['Barlow'] text-sm text-foreground">
                  {routes.length} Routen gefunden
                </h3>
                <span className="source-badge live">ORS Live</span>
              </div>

              {routes.map((r) => (
                <RouteCard
                  key={r.id}
                  route={r}
                  isSelected={selectedRoute === r.id}
                  onSelect={onSelectRoute}
                  onSave={onSaveRoute}
                  allRoutes={routes}
                />
              ))}

              {/* Data sources info */}
              {dataSources && (
                <div className="pt-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">Datenquellen</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(dataSources).map(([key, val]) => (
                      <span key={key} className={`source-badge ${val.includes("Live") || val.includes("live") || val.includes("ORS") || val.includes("Overpass") ? "live" : "demo"}`}>
                        {key}: {val}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </ScrollArea>
  );
}
