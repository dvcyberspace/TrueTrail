"""
Refresh the frontend's data files from the team's latest outputs.
Run from the repo root (the TrueTrail folder):   python part4/export_for_frontend.py

Reads : data/canonical/transactions.json, data/canonical/calls.json, outputs/network_graph.json
Writes: part4/frontend/src/transactions.json, calls.json, engineScores.json, engineGraph.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "part4" / "frontend" / "src"


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")
    print("wrote", name)


tx = ROOT / "data/canonical/transactions.json"
if tx.exists():
    dump("transactions.json", load(tx))
else:
    print("skipped transactions.json (data/canonical/transactions.json is missing; keeping the copy in the frontend)")

# each call appears twice in the CDR (OUT side and IN side); keep the OUT side
calls = load(ROOT / "data/canonical/calls.json")
dump("calls.json", [{k: c[k] for k in ("start_time", "duration_sec", "caller", "callee", "direction")}
                    for c in calls if c["direction"] == "OUT"])

graph = load(ROOT / "outputs/network_graph.json")
dump("engineScores.json", {
    n["value"]: {"risk": n.get("account_risk_score", 0), "reasons": n.get("account_risk_reasons", [])[:3]}
    for n in graph["nodes"] if n["kind"] == "account"
})

# the engine graph view: top 100 nodes by controller score (same picture as outputs/true_trail_network.html)
top = sorted(graph["nodes"], key=lambda n: -n.get("controller_score", 0))[:100]
ids = {n["id"] for n in top}
dump("engineGraph.json", {
    "nodes": [{"id": n["id"], "label": n["label"], "kind": n["kind"], "ctrl": n.get("controller_score", 0),
               "risk": n.get("account_risk_score"), "cluster": n.get("cluster_id"),
               "reasons": (n.get("controller_reasons", []) + n.get("account_risk_reasons", []))[:4]} for n in top],
    "edges": [{"source": e["source"], "target": e["target"], "kind": e["edge_kind"], "amount": e.get("amount", 0),
               "count": e.get("transaction_count", 0)} for e in graph["edges"] if e["source"] in ids and e["target"] in ids],
})
