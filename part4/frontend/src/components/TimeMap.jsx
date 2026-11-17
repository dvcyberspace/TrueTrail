import { MapContainer, TileLayer, CircleMarker, Popup, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const utc = (t) => String(t).replace("T", " ").replace("Z", " UTC");

export function TimelineView({ data }) {
  return (
    <div className="panel neon-card">
      <h2 className="panel-title">Event reconstruction</h2>
      <p className="muted small">Case {data.case_id} · {data.events.length} events</p>
      {data.sessions?.map((s) => (
        <div className="status warn" key={s.session_id}>
          {s.type.replace("_", " ")} · {s.duration_h} h · {utc(s.start_utc)}
          <div className="chips">{s.flags.map((f) => <span key={f}>{f.replaceAll("_", " ")}</span>)}</div>
        </div>
      ))}
      <div className="tl">
        {data.events.map((e) => (
          <div className="tl-item" key={e.event_id}>
            <i className={e.type === "UPI" ? "dot hot" : "dot"} />
            <div className="mono small muted">{utc(e.start_utc)}</div>
            <div className="tl-title">{e.type}{e.amount ? ` · ₹${e.amount.toLocaleString("en-IN")}` : ""}</div>
            <div className="small muted">
              {e.type === "UPI" ? `Paid to ${e.entities.payee_id}` : `Device ${e.entities.imei || "n/a"}`}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MapView({ data }) {
  const feats = data.geo_tracks?.[0]?.geojson?.features ?? [];
  const path = feats.find((f) => f.properties.kind === "path")?.geometry.coordinates.map((c) => [c[1], c[0]]) ?? [];
  const pings = feats.filter((f) => f.properties.kind === "ping");
  return (
    <div className="panel neon-card" style={{ padding: 0, overflow: "hidden", height: 560 }}>
      <MapContainer center={path[0] ?? [28.75, 77.05]} zoom={11} style={{ height: "100%", width: "100%", background: "#000" }}>
        <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
        <Polyline positions={path} pathOptions={{ color: "#22d3ee", weight: 2, opacity: 0.7 }} />
        {pings.map((p, i) => (
          <CircleMarker key={i} center={[p.geometry.coordinates[1], p.geometry.coordinates[0]]} radius={5}
            pathOptions={{ color: "#f472b6", fillColor: "#f472b6", fillOpacity: 0.7, weight: 1 }}>
            <Popup>{utc(p.properties.time_utc)}</Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
