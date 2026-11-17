// Builds the money-flow graph from Jaya's canonical transactions and flags suspicious accounts.
// These are HEURISTICS (tune the constants below), not a trained model.
const MIN_FLOW = 100000;      // an account must move at least this much (INR) to be flagged
const MIN_PASSTHROUGH = 0.8;  // forwarded / received must be at least 80%

export const ROLE = {
  victim:  { label: "Source of funds",     color: "#fbbf24" },
  mule:    { label: "Mule (pass-through)", color: "#f472b6" },
  cashout: { label: "Terminal account",    color: "#38bdf8" },
  other:   { label: "Other account",       color: "#64748b" },
};

export function buildGraph(txns) {
  const ok = txns.filter((t) => t.status === "SUCCESS");

  // 1) Identity: map UPI handles to account numbers so one person = one node
  const vpaToAcct = new Map();
  const names = new Map();
  for (const t of ok) {
    for (const s of ["sender", "receiver"]) {
      const a = t[s + "_account"], v = t[s + "_vpa"], n = t[s + "_name"];
      if (a && v) vpaToAcct.set(v, a);
      if (a && n && !names.has(a)) names.set(a, n);
    }
  }
  const idOf = (t, s) =>
    t[s + "_account"] || (t[s + "_vpa"] && vpaToAcct.get(t[s + "_vpa"])) || t[s + "_vpa"] || null;

  // 2) Aggregate nodes and edges
  const nodes = new Map();
  const getNode = (id, fallback) => {
    if (!nodes.has(id))
      nodes.set(id, {
        id, name: names.get(id) || fallback || id,
        inSum: 0, outSum: 0, inCnt: 0, outCnt: 0, cashIn: 0, cashOut: 0,
        firstOut: Infinity, devices: new Map(), ips: new Map(), role: "other",
      });
    return nodes.get(id);
  };
  const edges = new Map();
  for (const t of ok) {
    const s = idOf(t, "sender"), r = idOf(t, "receiver");
    const ts = Date.parse(t.timestamp);
    if (s && r) {
      const a = getNode(s, t.sender_name), b = getNode(r, t.receiver_name);
      a.outSum += t.amount; a.outCnt++; b.inSum += t.amount; b.inCnt++;
      a.firstOut = Math.min(a.firstOut, ts);
      if (t.device_id) a.devices.set(t.device_id, (a.devices.get(t.device_id) || 0) + 1);
      if (t.ip_address) a.ips.set(t.ip_address, (a.ips.get(t.ip_address) || 0) + 1);
      const k = s + ">" + r;
      const e = edges.get(k) || { source: s, target: r, total: 0, count: 0, first: Infinity, last: -Infinity, kind: "flow" };
      e.total += t.amount; e.count++; e.first = Math.min(e.first, ts); e.last = Math.max(e.last, ts);
      edges.set(k, e);
    } else if (r) getNode(r, t.receiver_name).cashIn += t.amount;   // cash deposit / NEFT credit
    else if (s) getNode(s, t.sender_name).cashOut += t.amount;      // ATM withdrawal
  }

  // 3) Roles
  for (const n of nodes.values()) {
    const hi = Math.max(n.inSum, n.outSum), lo = Math.min(n.inSum, n.outSum);
    n.volume = hi;
    n.passthrough = hi ? lo / hi : 0;
    if (lo >= MIN_FLOW && n.passthrough >= MIN_PASSTHROUGH) n.role = "mule";
    else if (n.outSum >= MIN_FLOW && n.outSum >= 3 * n.inSum) n.role = "victim";
    else if (n.inSum >= MIN_FLOW && n.inSum >= 3 * n.outSum) n.role = "cashout";
  }
  const suspicious = [...nodes.values()].filter((n) => n.role !== "other");
  const sus = new Set(suspicious.map((n) => n.id));

  // 4) Shared device / IP between flagged accounts
  const byDevice = new Map();
  for (const n of suspicious) for (const d of n.devices.keys()) {
    if (!byDevice.has(d)) byDevice.set(d, []);
    byDevice.get(d).push(n);
  }
  const shared = [];
  for (const [device, list] of byDevice) {
    for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
      const ips = [...list[i].ips.keys()].filter((ip) => list[j].ips.has(ip));
      shared.push({ source: list[i].id, target: list[j].id, kind: "shared", device, ips });
    }
  }

  // 5) Summary
  const flowEdges = [...edges.values()].filter((e) => sus.has(e.source) && sus.has(e.target));
  const stats = {
    accounts: nodes.size,
    flagged: suspicious.length,
    entered: flowEdges.filter((e) => nodes.get(e.source).role === "victim").reduce((s, e) => s + e.total, 0),
    routed: suspicious.filter((n) => n.role === "cashout").reduce((s, n) => s + n.inSum, 0),
    from: flowEdges.length ? Math.min(...flowEdges.map((e) => e.first)) : null,
    to: flowEdges.length ? Math.max(...flowEdges.map((e) => e.last)) : null,
  };
  return { nodes: [...nodes.values()], edges: [...edges.values()], shared, sus, stats };
}

// Returns fresh copies (the graph library mutates what it receives).
export function viewGraph(g, mode) {
  const label = (e) => "₹" + Math.round(e.total / 1000) + "k" + (e.count > 1 ? " ×" + e.count : "");
  if (mode === "all") {
    return {
      nodes: g.nodes.map((n) => ({ ...n })),
      links: [...g.edges, ...g.shared].map((e) => ({ ...e, label: e.kind === "flow" ? label(e) : "" })),
    };
  }
  // Order the chain by following the biggest outgoing flow from the source
  const inChain = g.nodes.filter((n) => g.sus.has(n.id));
  const flow = g.edges.filter((e) => g.sus.has(e.source) && g.sus.has(e.target));
  const ordered = [];
  const seen = new Set();
  let cur = inChain.find((n) => n.role === "victim") || inChain[0];
  while (cur && !seen.has(cur.id)) {
    ordered.push(cur); seen.add(cur.id);
    const next = flow.filter((e) => e.source === cur.id && !seen.has(e.target)).sort((a, b) => b.total - a.total)[0];
    cur = next && inChain.find((n) => n.id === next.target);
  }
  for (const n of inChain) if (!seen.has(n.id)) ordered.push(n);
  const ns = ordered.map((n, i, arr) => ({ ...n, fx: (i - (arr.length - 1) / 2) * 120, fy: i % 2 ? 34 : -34 }));
  const links = [...g.edges.filter((e) => g.sus.has(e.source) && g.sus.has(e.target)), ...g.shared]
    .map((e) => ({ ...e, label: e.kind === "flow" ? label(e) : "" }));
  return { nodes: ns, links };
}
