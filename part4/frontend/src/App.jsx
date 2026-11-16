import { useState, useEffect } from "react";
import "./App.css";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

// Leaflet icon fix
import L from "leaflet";
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

function App() {
  const [auditLog, setAuditLog] = useState([]);
  const [chainStatus, setChainStatus] = useState(null);
  const [file, setFile] = useState(null);
  const [caseId, setCaseId] = useState("C123");
  const [uploadStatus, setUploadStatus] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");

  // Part 3 Data Load
  const [timelineData, setTimelineData] = useState(null);

  useEffect(() => {
    // Load Part 3 JSON
    import("./timeline.json").then((data) =>
      setTimelineData(data.default || data),
    );
  }, []);

  const fetchAudit = async () => {
    try {
      const res = await fetch("http://localhost:8001/audit");
      if (!res.ok) throw new Error("Backend error");
      const data = await res.json();
      setAuditLog(data);

      const verifyRes = await fetch("http://localhost:8001/audit/verify");
      const verifyData = await verifyRes.json();
      setChainStatus(verifyData);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchAudit();
  }, []);

  const handleUpload = async () => {
    if (!file) return alert("Select a file!");
    const formData = new FormData();
    formData.append("file", file);
    try {
      setUploadStatus("Hashing...");
      const res = await fetch("http://localhost:8001/evidence/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setUploadStatus(`✅ Hash: ${data.sha256.substring(0, 15)}...`);
      fetchAudit();
    } catch (err) {
      setUploadStatus("❌ Error connecting to backend.");
    }
  };

  // Extract Polyline coordinates from GeoJSON
  const getPathCoords = () => {
    if (!timelineData || !timelineData.geo_tracks) return [];
    const feature = timelineData.geo_tracks[0].geojson.features.find(
      (f) => f.properties.kind === "path",
    );
    if (!feature) return [];
    // Leaflet wants [lat, lon], GeoJSON is [lon, lat]
    return feature.geometry.coordinates.map((coord) => [coord[1], coord[0]]);
  };

  return (
    <div
      style={{ display: "flex", minHeight: "100vh", fontFamily: "sans-serif" }}
    >
      {/* SIDEBAR */}
      <div
        style={{
          width: "250px",
          background: "#1e293b",
          color: "white",
          padding: "20px",
        }}
      >
        <h2 style={{ color: "#38bdf8" }}>🛡️ TrueTrail</h2>
        <p style={{ fontSize: "12px", color: "#94a3b8" }}>
          Evidence Integrity & Court Package
        </p>
        <hr style={{ borderColor: "#334155", margin: "20px 0" }} />
        <div
          style={{
            background: "#0f172a",
            padding: "15px",
            borderRadius: "8px",
          }}
        >
          <h4 style={{ margin: "0 0 10px 0" }}>Ingest Evidence</h4>
          <input
            type="file"
            onChange={(e) => setFile(e.target.files[0])}
            style={{ fontSize: "12px", marginBottom: "10px", color: "white" }}
          />
          <button
            onClick={handleUpload}
            style={{
              width: "100%",
              padding: "8px",
              background: "#3b82f6",
              color: "white",
              border: "none",
              borderRadius: "5px",
              cursor: "pointer",
            }}
          >
            Upload & Hash
          </button>
          {uploadStatus && (
            <p
              style={{ fontSize: "11px", color: "#4ade80", marginTop: "10px" }}
            >
              {uploadStatus}
            </p>
          )}
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div style={{ flex: 1, padding: "30px", background: "#f8fafc" }}>
        {/* TABS */}
        <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
          {["dashboard", "timeline", "map"].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: "10px 20px",
                background: activeTab === tab ? "#3b82f6" : "white",
                color: activeTab === tab ? "white" : "black",
                border: "1px solid #ccc",
                borderRadius: "5px",
                cursor: "pointer",
                textTransform: "capitalize",
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* DASHBOARD TAB */}
        {activeTab === "dashboard" && (
          <div>
            <h2>Chain of Custody Ledger</h2>
            <div
              style={{
                padding: "10px",
                background: chainStatus?.valid ? "#dcfce7" : "#fee2e2",
                borderRadius: "5px",
                marginBottom: "15px",
              }}
            >
              <strong>Chain Integrity: </strong>{" "}
              {chainStatus?.valid
                ? `✅ SECURE (${chainStatus.entries} entries)`
                : "❌ TAMPERED"}
            </div>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                background: "white",
              }}
            >
              <thead>
                <tr style={{ background: "#e2e8f0", textAlign: "left" }}>
                  <th style={{ padding: "10px", border: "1px solid #cbd5e1" }}>
                    File
                  </th>
                  <th style={{ padding: "10px", border: "1px solid #cbd5e1" }}>
                    SHA-256 Hash
                  </th>
                </tr>
              </thead>
              <tbody>
                {auditLog.map((row) => (
                  <tr key={row.id}>
                    <td
                      style={{ padding: "10px", border: "1px solid #cbd5e1" }}
                    >
                      {row.file_name}
                    </td>
                    <td
                      style={{
                        padding: "10px",
                        border: "1px solid #cbd5e1",
                        fontFamily: "monospace",
                        fontSize: "12px",
                      }}
                    >
                      {row.file_hash}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* TIMELINE TAB (Part 3 Data) */}
        {activeTab === "timeline" && timelineData && (
          <div
            style={{
              background: "white",
              padding: "20px",
              borderRadius: "10px",
            }}
          >
            <h2>Event Sequence Reconstruction</h2>
            <p style={{ color: "#64748b" }}>
              Case: {timelineData.case_id} | Window:{" "}
              {timelineData.parameters.windows_min[0]} min
            </p>

            <div
              style={{
                borderLeft: "2px solid #3b82f6",
                paddingLeft: "20px",
                marginTop: "20px",
              }}
            >
              {timelineData.events.map((evt) => (
                <div
                  key={evt.event_id}
                  style={{ marginBottom: "20px", position: "relative" }}
                >
                  <div
                    style={{
                      position: "absolute",
                      left: "-26px",
                      top: "5px",
                      width: "12px",
                      height: "12px",
                      borderRadius: "50%",
                      background: evt.type === "UPI" ? "#ef4444" : "#3b82f6",
                    }}
                  ></div>
                  <strong>{new Date(evt.start_utc).toLocaleString()}</strong> -{" "}
                  {evt.type}
                  {evt.amount && (
                    <span style={{ color: "#ef4444", marginLeft: "10px" }}>
                      ₹{evt.amount}
                    </span>
                  )}
                  <div style={{ fontSize: "14px", color: "#475569" }}>
                    {evt.type === "UPI"
                      ? `Paid to ${evt.entities.payee_id}`
                      : `Device: ${evt.entities.imei || "N/A"}`}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* MAP TAB (Part 3 Data) */}
        {activeTab === "map" && timelineData && (
          <div
            style={{
              height: "600px",
              borderRadius: "10px",
              overflow: "hidden",
            }}
          >
            <MapContainer
              center={[28.753477, 77.057639]}
              zoom={12}
              style={{ height: "100%", width: "100%" }}
            >
              <TileLayer
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              />

              {/* Render Geo Track Path */}
              <Polyline
                pathOptions={{ color: "#38bdf8", weight: 4 }}
                positions={getPathCoords()}
              />

              {/* Render Pings */}
              {timelineData.geo_tracks[0].geojson.features
                .filter((f) => f.properties.kind === "ping")
                .map((ping, idx) => (
                  <Marker
                    key={idx}
                    position={[
                      ping.geometry.coordinates[1],
                      ping.geometry.coordinates[0],
                    ]}
                  >
                    <Popup>
                      Ping at:{" "}
                      {new Date(ping.properties.time_utc).toLocaleString()}{" "}
                      <br />
                      Radius: {ping.properties.radius_m}m
                    </Popup>
                  </Marker>
                ))}
            </MapContainer>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
