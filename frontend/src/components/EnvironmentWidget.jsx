import {
  Cloud, Droplets, Wind, Thermometer, AlertTriangle, CheckCircle, Waves, Gauge,
} from "lucide-react";
import { useState } from "react";

function DangerBadge({ level }) {
  if (level === "high") return <span className="inline-flex items-center gap-1 text-[10px] font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded"><AlertTriangle className="h-3 w-3" />Gefahr</span>;
  if (level === "medium") return <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded"><AlertTriangle className="h-3 w-3" />Vorsicht</span>;
  return <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded"><CheckCircle className="h-3 w-3" />OK</span>;
}

function AqiBadge({ aqi, label }) {
  const colors = { 1: "text-emerald-600 bg-emerald-50", 2: "text-emerald-600 bg-emerald-50", 3: "text-amber-600 bg-amber-50", 4: "text-red-600 bg-red-50", 5: "text-red-600 bg-red-50" };
  return <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${colors[aqi] || colors[1]}`}>{label}</span>;
}

function SourceTag({ source }) {
  return <span className={`source-badge ${source === "live" ? "live" : "demo"}`}>{source === "live" ? "Live" : "Demo"}</span>;
}

export default function EnvironmentWidget({ data }) {
  const [expanded, setExpanded] = useState(false);

  if (!data) {
    return (
      <div className="glass-panel rounded-xl px-4 py-3 animate-pulse" data-testid="env-widget-loading">
        <div className="h-4 w-32 bg-slate-200 rounded" />
      </div>
    );
  }

  const weather = data.weather?.data || {};
  const aare = data.aare?.data || {};
  const air = data.air_quality?.data || {};
  const warningLevel = data.warning_level || "ok";
  const warnings = data.warnings || [];

  return (
    <div className="glass-panel rounded-xl overflow-hidden max-w-[280px]" data-testid="env-widget">
      {/* Warning banner */}
      {warningLevel !== "ok" && warnings.length > 0 && (
        <div className={`px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 ${warningLevel === "danger" ? "bg-red-500 text-white" : "bg-amber-400 text-amber-900"}`}>
          <AlertTriangle className="h-3 w-3" />
          {warnings[0]}
        </div>
      )}

      <button
        className="w-full px-4 py-3 text-left hover:bg-slate-50/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
        data-testid="env-widget-toggle"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Umweltstatus</span>
          {warningLevel === "ok" && <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />}
        </div>

        {/* Compact row */}
        <div className="flex items-center gap-3 mt-2">
          <div className="flex items-center gap-1.5">
            <Thermometer className="h-3.5 w-3.5 text-sky-500" />
            <span className="text-sm font-semibold text-foreground">{Math.round(weather.temp || 0)}&deg;C</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Waves className="h-3.5 w-3.5 text-cyan-500" />
            <span className="text-sm font-semibold text-foreground">{Math.round(aare.temperature || 0)}&deg;C</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Gauge className="h-3.5 w-3.5 text-violet-500" />
            <span className="text-sm font-semibold text-foreground">AQI {air.aqi || "-"}</span>
          </div>
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-100 pt-3 slide-up-enter">
          {/* Weather */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Cloud className="h-3.5 w-3.5 text-sky-500" /> Wetter
              </span>
              <SourceTag source={data.weather?.source} />
            </div>
            <p className="text-xs text-muted-foreground capitalize">{weather.description || "-"}</p>
            <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1"><Thermometer className="h-3 w-3" /> {weather.temp?.toFixed(1)}&deg;C</span>
              <span className="flex items-center gap-1"><Wind className="h-3 w-3" /> {weather.wind_speed?.toFixed(1)} m/s</span>
              <span className="flex items-center gap-1"><Droplets className="h-3 w-3" /> {weather.humidity}%</span>
            </div>
          </div>

          {/* Aare */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Waves className="h-3.5 w-3.5 text-cyan-500" /> Aare
              </span>
              <div className="flex items-center gap-1.5">
                <DangerBadge level={aare.danger_level} />
                <SourceTag source={data.aare?.source} />
              </div>
            </div>
            <div className="flex gap-3 text-xs text-muted-foreground">
              <span>Temp: {aare.temperature}&deg;C</span>
              <span>Abfluss: {aare.flow} m&sup3;/s</span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">{aare.danger_text}</p>
          </div>

          {/* Air Quality */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Gauge className="h-3.5 w-3.5 text-violet-500" /> Luftqualitaet
              </span>
              <div className="flex items-center gap-1.5">
                <AqiBadge aqi={air.aqi} label={air.aqi_label} />
                <SourceTag source={data.air_quality?.source} />
              </div>
            </div>
            <div className="flex gap-3 text-xs text-muted-foreground">
              <span>PM2.5: {air.pm25?.toFixed(1)}</span>
              <span>PM10: {air.pm10?.toFixed(1)}</span>
            </div>
          </div>

          {/* Flood */}
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500" /> Hochwasser
              </span>
              <div className="flex items-center gap-1.5">
                <DangerBadge level={data.flood?.data?.warning_active ? "high" : "low"} />
                <SourceTag source={data.flood?.source} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
