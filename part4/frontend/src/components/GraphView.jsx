import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { buildGraph, viewGraph, ROLE } from "../graphLogic.js";

const inr = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
const hhmm = (t) => new Date(t).toISOString().slice(11, 16);

export default function GraphView({ transactions }) {
  const graph = useMemo(() => buildGraph(transactions), [transactions]);
  const [mode, setMode] = useState("network"); // network | all
  const [selected, setSelected] = useState(null);
  const data = useMemo(() => viewGraph(graph, mode), [graph, mode]);
  const wrap = useRef(null);
  const fg = useRef(null);
  const [w, setW] = useState(800);

  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    if (wrap.current) ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);
  useEffect(() => {
    setSelected(null);
    const t = setTimeout(() => fg.current?.zoomToFit(400, 70), 350);
    return () => clearTimeout(t);
  }, [mode, w]);

  const { stats, shared } = graph;
  const nameOf = (id) => graph.nodes.find((n) => n.id === id)?.name ?? id;

  const drawNode = (n, ctx, gs) => {
    const flagged = n.role !== "other";
    const r = flagged ? 6 + Math.min(8, Math.sqrt(n.volume / 1000) * 0.45) : 3;
    const color = ROLE[n.role].color;
    ctx.save();
    ctx.shadowColor = color; ctx.shadowBlur = flagged ? 14 : 0;
    ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color + (flagged ? "cc" : "99"); ctx.fill();
    ctx.restore();
    if (selected?.id === n.id) {
      ctx.beginPath(); ctx.arc(n.x, n.y, r + 3, 0, 2 * Math.PI);
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.2 / gs; ctx.stroke();
    }
    if (flagged || gs > 2) {
      ctx.font = `${(flagged ? 11 : 9) / gs}px Inter, sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.fillStyle = flagged ? "rgba(255,255,255,.88)" : "rgba(255,255,255,.55)";
      ctx.fillText(n.name, n.x, n.y + r + 3 / gs);
    }
  };
  const drawLabel = (l, ctx, gs) => {
    if (!l.label || typeof l.source !== "object" || (mode === "all" && gs < 1.6)) return;
    ctx.font = `${9 / gs}px Inter, sans-serif`;
    ctx.textAlign = "center"; ctx.textBaseline = "bottom";
    ctx.fillStyle = "rgba(255,255,255,.5)";
    ctx.fillText(l.label, (l.source.x + l.target.x) / 2, (l.source.y + l.target.y) / 2 - 3 / gs);
  };

  return (
    <div className="panel neon-card graph-panel">
      <div className="graph-head">
        <div>
          <h2 className="panel-title">Mule network</h2>
          <p className="muted small">
            Synthetic case · {transactions.length} transactions · {stats.accounts} accounts
          </p>
        </div>
        <div className="seg">
          <button className={mode === "network" ? "on" : ""} onClick={() => setMode("network")}>Suspicious chain</button>
          <button className={mode === "all" ? "on" : ""} onClick={() => setMode("all")}>All accounts</button>
        </div>
      </div>

      <div className="stat-row">
        <div><b>{stats.flagged}</b><span>accounts flagged</span></div>
        <div><b>{inr(stats.entered)}</b><span>entered the chain</span></div>
        <div><b>{inr(stats.routed)}</b><span>reached the end</span></div>
        {stats.from && <div><b>{hhmm(stats.from)}–{hhmm(stats.to)}</b><span>UTC window</span></div>}
      </div>

      <div ref={wrap} className="graph-canvas">
        <ForceGraph2D
          ref={fg}
          graphData={data}
          width={w}
          height={mode === "network" ? 380 : 560}
          backgroundColor="rgba(0,0,0,0)"
          nodeRelSize={6}
          nodeCanvasObject={drawNode}
          nodePointerAreaPaint={(n, color, ctx) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(n.x, n.y, 12, 0, 2 * Math.PI); ctx.fill(); }}
          linkColor={(l) => (l.kind === "shared" ? "rgba(167,139,250,.9)" : "rgba(255,255,255,.28)")}
          linkWidth={(l) => (l.kind === "shared" ? 1.4 : Math.max(0.6, Math.log10(l.total) - 3))}
          linkLineDash={(l) => (l.kind === "shared" ? [4, 3] : null)}
          linkCurvature={(l) => (l.kind === "shared" ? 0.8 : 0)}
          linkDirectionalArrowLength={(l) => (l.kind === "shared" ? 0 : mode === "network" ? 6 : 3)}
          linkDirectionalArrowRelPos={0.92}
          linkCanvasObjectMode={() => "after"}
          linkCanvasObject={drawLabel}
          onNodeClick={(n) => setSelected(n)}
          onBackgroundClick={() => setSelected(null)}
          cooldownTicks={mode === "network" ? 60 : 120}
          onEngineStop={() => mode === "all" && fg.current?.zoomToFit(400, 50)}
        />
        {selected && (
          <div className="node-card">
            <button className="x" onClick={() => setSelected(null)} aria-label="Close">×</button>
            <div className="nc-role" style={{ color: ROLE[selected.role].color }}>{ROLE[selected.role].label}</div>
            <h3>{selected.name}</h3>
            <div className="mono small muted">{selected.id}</div>
            <dl>
              <dt>Received</dt><dd>{inr(selected.inSum)} <span className="muted">({selected.inCnt})</span></dd>
              <dt>Sent</dt><dd>{inr(selected.outSum)} <span className="muted">({selected.outCnt})</span></dd>
              {selected.role === "mule" && <><dt>Passed on</dt><dd>{Math.round(selected.passthrough * 100)}% of what it received</dd></>}
              {(selected.cashIn > 0 || selected.cashOut > 0) && (
                <><dt>Cash</dt><dd>{selected.cashIn > 0 && `${inr(selected.cashIn)} in `}{selected.cashOut > 0 && `${inr(selected.cashOut)} out`}</dd></>
              )}
            </dl>
          </div>
        )}
      </div>

      <div className="legend">
        {Object.entries(ROLE).map(([k, v]) => (
          <span key={k}><i style={{ background: v.color }} />{v.label}</span>
        ))}
        <span><i className="dash" />Shared device / IP</span>
      </div>

      {shared.length > 0 && (
        <div className="evidence">
          <h3>Link evidence</h3>
          {shared.map((s, i) => (
            <p key={i}>
              <b>{nameOf(s.source)}</b> and <b>{nameOf(s.target)}</b> paid from the same device
              (<span className="mono">{s.device.slice(0, 8)}…</span>){s.ips.length > 0 && <> and the same IP (<span className="mono">{s.ips[0]}</span>)</>}.
            </p>
          ))}
        </div>
      )}
      <p className="muted small note">Roles are a heuristic: an account that forwards at least 80% of what it receives, moving ₹1 lakh or more, is flagged as a mule.</p>
    </div>
  );
}
