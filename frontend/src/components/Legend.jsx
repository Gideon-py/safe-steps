import { useState } from "react";
import { ChevronDown, ChevronUp, Shield, Zap, Scale, AlertTriangle, Circle } from "lucide-react";

const LEGEND_ITEMS = [
  {
    category: "Routen",
    items: [
      { label: "Sicherste Route", color: "#10B981", type: "line", weight: 6 },
      { label: "Ausgewogene Route", color: "#F59E0B", type: "dashed", weight: 4 },
      { label: "Schnellste Route", color: "#64748B", type: "dashed", weight: 3 },
    ],
  },
  {
    category: "Gefahrenzonen",
    items: [
      { label: "Hohes Risiko", color: "#EF4444", type: "circle" },
      { label: "Mittleres Risiko", color: "#F59E0B", type: "circle" },
    ],
  },
  {
    category: "Markierungen",
    items: [
      { label: "Schule", color: "#3B82F6", type: "dot" },
      { label: "Startpunkt", color: "#10B981", type: "dot" },
    ],
  },
];

function LineIcon({ color, dashed, weight = 3 }) {
  return (
    <svg width="28" height="12" viewBox="0 0 28 12" className="flex-shrink-0">
      <line
        x1="2" y1="6" x2="26" y2="6"
        stroke={color}
        strokeWidth={weight}
        strokeLinecap="round"
        strokeDasharray={dashed ? "4 4" : "none"}
      />
    </svg>
  );
}

function CircleIcon({ color }) {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" className="flex-shrink-0">
      <circle cx="10" cy="10" r="8" fill={color} fillOpacity={0.25} stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function DotIcon({ color }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" className="flex-shrink-0">
      <circle cx="7" cy="7" r="5" fill={color} />
    </svg>
  );
}

export default function Legend() {
  const [open, setOpen] = useState(true);

  return (
    <div
      className="glass-panel rounded-xl overflow-hidden select-none"
      style={{ minWidth: 180 }}
      data-testid="map-legend"
    >
      <button
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-50/50 transition-colors"
        onClick={() => setOpen(!open)}
        data-testid="legend-toggle"
      >
        <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
          Legende
        </span>
        {open ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-2.5 slide-up-enter">
          {LEGEND_ITEMS.map((group) => (
            <div key={group.category}>
              <p className="text-[10px] font-semibold text-muted-foreground mb-1.5 uppercase tracking-wider">
                {group.category}
              </p>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <div key={item.label} className="flex items-center gap-2">
                    {item.type === "line" && (
                      <LineIcon color={item.color} weight={item.weight} />
                    )}
                    {item.type === "dashed" && (
                      <LineIcon color={item.color} dashed weight={item.weight} />
                    )}
                    {item.type === "circle" && <CircleIcon color={item.color} />}
                    {item.type === "dot" && <DotIcon color={item.color} />}
                    <span className="text-[11px] text-foreground">{item.label}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
