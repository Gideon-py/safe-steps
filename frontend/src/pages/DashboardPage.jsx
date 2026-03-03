import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/App";
import api from "@/lib/api";
import MapView from "@/components/MapView";
import RoutePanel from "@/components/RoutePanel";
import EnvironmentWidget from "@/components/EnvironmentWidget";
import Legend from "@/components/Legend";
import { Button } from "@/components/ui/button";
import { Shield, LogOut, User } from "lucide-react";
import { toast } from "sonner";

export default function DashboardPage() {
  const { user, token, logout } = useAuth();
  const [schools, setSchools] = useState([]);
  const [envData, setEnvData] = useState(null);
  const [startPoint, setStartPoint] = useState(null);
  const [selectedSchool, setSelectedSchool] = useState(null);
  const [departureTime, setDepartureTime] = useState("07:30");
  const [routes, setRoutes] = useState([]);
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [dataSources, setDataSources] = useState(null);
  const [routingSource, setRoutingSource] = useState(null);
  const [calculating, setCalculating] = useState(false);

  useEffect(() => {
    api.getSchools().then(setSchools).catch(() => toast.error("Schulen konnten nicht geladen werden"));
    api.getEnvironment().then(setEnvData).catch(() => toast.error("Umweltdaten nicht verfuegbar"));
  }, []);

  const handleMapClick = useCallback((latlng) => {
    setStartPoint({ lat: latlng.lat, lng: latlng.lng });
    setRoutes([]);
    setSelectedRoute(null);
  }, []);

  const handleSchoolClick = useCallback((school) => {
    setSelectedSchool(school);
    setRoutes([]);
    setSelectedRoute(null);
  }, []);

  const handleRouteClick = useCallback((routeId) => {
    setSelectedRoute(routeId);
  }, []);

  const calculateRoutes = async () => {
    if (!startPoint || !selectedSchool) {
      toast.error("Bitte Startpunkt und Schule waehlen");
      return;
    }
    setCalculating(true);
    try {
      const res = await api.calculateRoutes(
        startPoint.lat, startPoint.lng, selectedSchool.id, departureTime
      );
      const routeList = res.routes || [];
      setRoutes(routeList);
      setDataSources(res.data_sources || null);
      setRoutingSource(res.routing_source || null);

      // Auto-select safest route
      const safest = routeList.find((r) => r.is_safest);
      setSelectedRoute(safest?.id || routeList[0]?.id || null);

      toast.success(`${routeList.length} Routen berechnet – Sicherste Route ausgewaehlt`);
    } catch (err) {
      const msg = err.response?.data?.detail || "Routenberechnung fehlgeschlagen";
      toast.error(msg);
    } finally {
      setCalculating(false);
    }
  };

  const saveRoute = async (route) => {
    try {
      await api.saveRoute(token, route.is_safest ? "Sicherste Route" : `Route ${route.id}`, route);
      toast.success("Route gespeichert!");
    } catch {
      toast.error("Speichern fehlgeschlagen");
    }
  };

  return (
    <div className="h-screen w-screen relative overflow-hidden" data-testid="dashboard">
      <MapView
        schools={schools}
        startPoint={startPoint}
        selectedSchool={selectedSchool}
        routes={routes}
        selectedRoute={selectedRoute}
        onMapClick={handleMapClick}
        onSchoolClick={handleSchoolClick}
        onRouteClick={handleRouteClick}
      />

      <div className="absolute inset-0 pointer-events-none z-10">
        {/* Logo */}
        <div className="absolute top-4 left-4 pointer-events-auto flex items-center gap-3">
          <div className="glass-panel rounded-xl px-4 py-2.5 flex items-center gap-2.5">
            <Shield className="h-5 w-5 text-primary" />
            <span className="font-bold font-['Barlow'] text-sm tracking-tight text-foreground">SafeWay Bern</span>
          </div>
        </div>

        {/* Environment widget */}
        <div className="absolute top-16 right-4 pointer-events-auto" style={{ zIndex: 20 }}>
          <EnvironmentWidget data={envData} />
        </div>

        {/* User info + logout */}
        <div className="absolute bottom-14 right-4 pointer-events-auto">
          <div className="glass-panel rounded-xl px-3 py-2 flex items-center gap-2">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-medium text-foreground hidden sm:inline">{user?.name}</span>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={logout} data-testid="logout-btn">
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Map Legend – bottom right, above user info */}
        <div className="absolute bottom-28 right-4 pointer-events-auto" style={{ zIndex: 15 }}>
          <Legend />
        </div>

        {/* Route panel */}
        <div className="absolute left-4 top-16 bottom-16 w-[360px] pointer-events-auto overflow-hidden max-w-[calc(100vw-2rem)]">
          <RoutePanel
            startPoint={startPoint}
            selectedSchool={selectedSchool}
            schools={schools}
            departureTime={departureTime}
            onDepartureTimeChange={setDepartureTime}
            onSchoolSelect={handleSchoolClick}
            onCalculate={calculateRoutes}
            calculating={calculating}
            routes={routes}
            selectedRoute={selectedRoute}
            onSelectRoute={setSelectedRoute}
            onSaveRoute={saveRoute}
            dataSources={dataSources}
            routingSource={routingSource}
          />
        </div>

        {/* Map hint */}
        {!startPoint && (
          <div className="map-hint">
            <div className="glass-panel rounded-full px-5 py-2.5 text-sm font-medium text-foreground">
              Klicke auf die Karte, um deinen Startpunkt zu setzen
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
