import { useEffect, useState } from "react";

const API = "http://127.0.0.1:8000";

export default function App() {
  const [audit, setAudit] = useState([]);
  const [chain, setChain] = useState(null);
  const [results, setResults] = useState({});

  const refresh = async () => {
    setAudit(await (await fetch(`${API}/audit`)).json());
    setChain(await (await fetch(`${API}/audit/verify`)).json());
  };
  useEffect(() => {
    refresh();
  }, []);

  const upload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    await fetch(`${API}/evidence/upload`, { method: "POST", body: fd });
    e.target.value = "";
    refresh();
  };

  const verify = async (name) => {
    const r = await (
      await fetch(`${API}/evidence/${encodeURIComponent(name)}/verify`)
    ).json();
    setResults((p) => ({ ...p, [name]: r.match }));
    refresh();
  };

  const evidence = audit.filter((a) => a.action === "INGEST");

  return (
    <div style={{ padding: 24, fontFamily: "sans-serif" }}>
      <h2>Evidence Integrity</h2>
      <p>
        Audit chain:{" "}
        {chain
          ? chain.valid
            ? "✅ Valid"
            : `❌ Broken at entry ${chain.broken_at_entry}`
          : "..."}
      </p>

      <input type="file" onChange={upload} />

      <h3>Evidence</h3>
      <table border="1" cellPadding="6">
        <thead>
          <tr>
            <th>File</th>
            <th>SHA-256</th>
            <th>Ingested (UTC)</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((e) => (
            <tr key={e.id}>
              <td>{e.file}</td>
              <td style={{ fontFamily: "monospace" }}>
                {e.file_hash.slice(0, 16)}…
              </td>
              <td>{e.ts}</td>
              <td>
                {results[e.file] === undefined
                  ? "-"
                  : results[e.file]
                    ? "✅ Intact"
                    : "❌ Tampered"}
              </td>
              <td>
                <button onClick={() => verify(e.file)}>Verify hash</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Audit log</h3>
      <table border="1" cellPadding="6">
        <thead>
          <tr>
            <th>#</th>
            <th>Time</th>
            <th>Actor</th>
            <th>Action</th>
            <th>File</th>
            <th>Entry hash</th>
          </tr>
        </thead>
        <tbody>
          {audit.map((a) => (
            <tr key={a.id}>
              <td>{a.id}</td>
              <td>{a.ts}</td>
              <td>{a.actor}</td>
              <td>{a.action}</td>
              <td>{a.file}</td>
              <td style={{ fontFamily: "monospace" }}>
                {a.entry_hash.slice(0, 12)}…
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
