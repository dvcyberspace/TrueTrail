import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [auditLog, setAuditLog] = useState([]);
  const [chainStatus, setChainStatus] = useState(null);
  const [file, setFile] = useState(null);
  const [caseId, setCaseId] = useState("CR-2026-001");
  const [uploadStatus, setUploadStatus] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");

  const fetchAudit = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8001/audit");
      const data = await res.json();
      setAuditLog(data);

      const verifyRes = await fetch("http://127.0.0.1:8001/audit/verify");
      const verifyData = await verifyRes.json();
      setChainStatus(verifyData);
    } catch (err) {
      console.error("Error fetching audit data", err);
    }
  };

  useEffect(() => {
    fetchAudit();
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploadStatus("Uploading and Hashing...");
      const res = await fetch("http://127.0.0.1:8001/evidence/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setUploadStatus(`✅ Uploaded! Hash: ${data.sha256.substring(0, 15)}...`);
      fetchAudit(); // Refresh table
    } catch (err) {
      setUploadStatus("❌ Upload failed.");
    }
  };

  const handleGenerateReport = async () => {
    if (auditLog.length === 0) return alert("No files in audit log!");
    const lastFile = auditLog[auditLog.length - 1];

    try {
      const res = await fetch(
        `http://127.0.0.1:8001/report?file_name=${lastFile.file}&file_hash=${lastFile.file_hash}&case_id=${caseId}`,
        {
          method: "POST",
        },
      );
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `BSA_Report_${caseId}.pdf`;
      a.click();
    } catch (err) {
      alert("Failed to generate PDF");
    }
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
            style={{ fontSize: "12px", marginBottom: "10px" }}
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
          {["dashboard", "graph", "timeline"].map((tab) => (
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
              <strong>Chain Integrity: </strong>
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
                    ID
                  </th>
                  <th style={{ padding: "10px", border: "1px solid #cbd5e1" }}>
                    Time
                  </th>
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
                      {row.id}
                    </td>
                    <td
                      style={{
                        padding: "10px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                      }}
                    >
                      {row.ts}
                    </td>
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

        {/* GRAPH TAB (MOCK) */}
        {activeTab === "graph" && (
          <div>
            <h2>Mule Network Graph</h2>
            <div
              style={{
                height: "400px",
                background: "#e2e8f0",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "10px",
              }}
            >
              <p style={{ color: "#64748b" }}>
                [Graph Visualization from Member 2 will render here]
              </p>
            </div>
          </div>
        )}

        {/* TIMELINE TAB (MOCK) */}
        {activeTab === "timeline" && (
          <div>
            <h2>Spatiotemporal Timeline</h2>
            <div
              style={{
                height: "400px",
                background: "#e2e8f0",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "10px",
              }}
            >
              <p style={{ color: "#64748b" }}>
                [Timeline Map from Member 3 will render here]
              </p>
            </div>
          </div>
        )}

        {/* BSA REPORT SECTION */}
        <div
          style={{
            marginTop: "40px",
            background: "white",
            padding: "20px",
            borderRadius: "10px",
            border: "1px solid #cbd5e1",
          }}
        >
          <h3>⚖️ BSA 2023 Section 63 Certificate</h3>
          <p>
            Generate court-admissible evidence certificate for the last uploaded
            file.
          </p>
          <input
            type="text"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            placeholder="Case ID"
            style={{
              padding: "8px",
              marginRight: "10px",
              border: "1px solid #ccc",
              borderRadius: "5px",
            }}
          />
          <button
            onClick={handleGenerateReport}
            style={{
              padding: "8px 15px",
              background: "#10b981",
              color: "white",
              border: "none",
              borderRadius: "5px",
              cursor: "pointer",
            }}
          >
            Download BSA PDF
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
