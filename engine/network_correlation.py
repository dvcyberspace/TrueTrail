"""Network correlation and mule-mastermind analysis."""
import json
import os
import itertools
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from engine.data_source import load_all, data_source_description

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GRAPH_JSON_FILE = os.path.join(OUTPUT_DIR, "network_graph.json")
COMMUNITIES_FILE = os.path.join(OUTPUT_DIR, "network_communities.json")
CONTROLLERS_FILE = os.path.join(OUTPUT_DIR, "network_controller_candidates.json")
FUND_FLOW_FILE = os.path.join(OUTPUT_DIR, "fund_flow_analysis.json")

KIND_ACCOUNT = "account"
KIND_VPA = "vpa"
KIND_PHONE = "phone"
KIND_DEVICE = "device"
KIND_IP = "ip_address"

EDGE_TRANSFERRED = "TRANSFERRED"
EDGE_USED_DEVICE = "USED_DEVICE"
EDGE_LOGGED_FROM = "LOGGED_FROM"
EDGE_IDENTITY = "IDENTITY_LINK"

HIGH_RISK_THRESHOLD = 0.40
VELOCITY_WINDOW_MINUTES = 30

def _clean(value: Any) -> str:
    if value is None: return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null", "nat"}: return ""
    return text

def _node_id(kind: str, value: str) -> str: return f"{kind}:{value}"

def _parse_iso(timestamp: Any) -> Optional[datetime]:
    text = _clean(timestamp)
    if not text: return None
    try: return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception: return None

def _add_node(graph: nx.DiGraph, node_id: str, kind: str, label: str = None, **attrs) -> None:
    if node_id in graph: return
    graph.add_node(node_id, kind=kind, label=label or node_id, **attrs)

def _add_edge(graph: nx.DiGraph, source: str, target: str, kind: str, evidence: str = None, **attrs) -> None:
    if not source or not target or source == target: return
    if graph.has_edge(source, target):
        edge = graph[source][target]
        if edge.get("edge_kind") == kind:
            edge["occurrences"] = edge.get("occurrences", 1) + 1
            if evidence: edge.setdefault("evidence_refs", []).append(evidence)
            if kind == EDGE_TRANSFERRED:
                edge["amount"] = edge.get("amount", 0) + attrs.get("amount", 0)
                edge["transaction_count"] = edge.get("transaction_count", 0) + 1
                if attrs.get("timestamp"): edge.setdefault("timestamps", []).append(attrs["timestamp"])
        else:
            kinds = edge.setdefault("secondary_kinds", [])
            if kind not in kinds: kinds.append(kind)
            if evidence: edge.setdefault("evidence_refs", []).append(evidence)
        return

    payload = {"edge_kind": kind, "occurrences": 1}
    if evidence: payload["evidence_refs"] = [evidence]
    if kind == EDGE_TRANSFERRED:
        payload["amount"] = attrs.get("amount", 0)
        payload["transaction_count"] = 1
        payload["timestamps"] = [attrs["timestamp"]] if attrs.get("timestamp") else []
    if attrs.get("link_type"): payload["link_types"] = [attrs["link_type"]]
    graph.add_edge(source, target, **payload)

def _is_digital_edge(data: Dict[str, Any]) -> bool:
    if data.get("edge_kind") != EDGE_TRANSFERRED: return True
    return any(k != EDGE_TRANSFERRED for k in data.get("secondary_kinds", []))

def _primary_account_node(graph: nx.DiGraph, account: str, vpa: str, evidence: str, role_hint: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    account_node, vpa_node = None, None
    if account:
        account_node = _node_id(KIND_ACCOUNT, account)
        _add_node(graph, account_node, KIND_ACCOUNT, label=account, role=role_hint, value=account)
    if vpa:
        vpa_node = _node_id(KIND_VPA, vpa)
        _add_node(graph, vpa_node, KIND_VPA, label=vpa, role=role_hint, value=vpa)
    if account_node and vpa_node:
        _add_edge(graph, account_node, vpa_node, EDGE_IDENTITY, evidence=evidence, link_type="account_vpa")
        _add_edge(graph, vpa_node, account_node, EDGE_IDENTITY, evidence=evidence, link_type="account_vpa")
    return (account_node or vpa_node), account_node, vpa_node

def _build_transfer_graph(graph: nx.DiGraph) -> nx.DiGraph:
    tg = nx.DiGraph()
    for source, target, data in graph.edges(data=True):
        if data.get("edge_kind") == EDGE_TRANSFERRED: tg.add_edge(source, target, **data)
    return tg

def build_graph(transactions: List[Dict[str, Any]], calls: List[Dict[str, Any]], ip_sessions: List[Dict[str, Any]]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for txn in transactions:
        if _clean(txn.get("status")).upper() != "SUCCESS": continue
        amount, timestamp, txn_id = float(txn.get("amount") or 0), txn.get("timestamp"), _clean(txn.get("txn_id"))
        sender_account, sender_vpa = _clean(txn.get("sender_account")), _clean(txn.get("sender_vpa"))
        receiver_account, receiver_vpa = _clean(txn.get("receiver_account")), _clean(txn.get("receiver_vpa"))
        sender_phone, device_id, ip_address = _clean(txn.get("sender_mobile")), _clean(txn.get("device_id")), _clean(txn.get("ip_address"))

        sender_primary, _, _ = _primary_account_node(graph, sender_account, sender_vpa, txn_id, "sender")
        receiver_primary, _, _ = _primary_account_node(graph, receiver_account, receiver_vpa, txn_id, "receiver")
        if sender_primary and receiver_primary:
            _add_edge(graph, sender_primary, receiver_primary, EDGE_TRANSFERRED, evidence=txn_id, amount=amount, timestamp=timestamp)

        if sender_phone and sender_primary:
            phone_node = _node_id(KIND_PHONE, sender_phone)
            _add_node(graph, phone_node, KIND_PHONE, label=sender_phone, value=sender_phone)
            _add_edge(graph, phone_node, sender_primary, EDGE_IDENTITY, evidence=txn_id, link_type="phone_account")
            _add_edge(graph, sender_primary, phone_node, EDGE_IDENTITY, evidence=txn_id, link_type="phone_account")

        if device_id and sender_primary:
            device_node = _node_id(KIND_DEVICE, device_id)
            _add_node(graph, device_node, KIND_DEVICE, label=device_id, value=device_id)
            _add_edge(graph, sender_primary, device_node, EDGE_USED_DEVICE, evidence=txn_id)
            _add_edge(graph, device_node, sender_primary, EDGE_USED_DEVICE, evidence=txn_id)

        if ip_address and sender_primary:
            ip_node = _node_id(KIND_IP, ip_address)
            _add_node(graph, ip_node, KIND_IP, label=ip_address, value=ip_address)
            _add_edge(graph, sender_primary, ip_node, EDGE_LOGGED_FROM, evidence=txn_id)
            _add_edge(graph, ip_node, sender_primary, EDGE_LOGGED_FROM, evidence=txn_id)

    for call in calls:
        record_id, caller, target, imei = _clean(call.get("record_id")), _clean(call.get("caller")), _clean(call.get("target_number")), _clean(call.get("imei"))
        for phone in (caller, target):
            if phone: _add_node(graph, _node_id(KIND_PHONE, phone), KIND_PHONE, label=phone, value=phone)
        if imei:
            device_node = _node_id(KIND_DEVICE, imei)
            _add_node(graph, device_node, KIND_DEVICE, label=imei, value=imei)
            for phone in (target, caller):
                if not phone: continue
                phone_node = _node_id(KIND_PHONE, phone)
                _add_edge(graph, phone_node, device_node, EDGE_USED_DEVICE, evidence=record_id)
                _add_edge(graph, device_node, phone_node, EDGE_USED_DEVICE, evidence=record_id)

    for session in ip_sessions:
        session_id, msisdn, src_ip, imei = _clean(session.get("session_id")), _clean(session.get("msisdn")), _clean(session.get("src_ip")), _clean(session.get("imei"))
        if not msisdn: continue
        phone_node = _node_id(KIND_PHONE, msisdn)
        _add_node(graph, phone_node, KIND_PHONE, label=msisdn, value=msisdn)
        if src_ip:
            ip_node = _node_id(KIND_IP, src_ip)
            _add_node(graph, ip_node, KIND_IP, label=src_ip, value=src_ip)
            _add_edge(graph, phone_node, ip_node, EDGE_LOGGED_FROM, evidence=session_id)
            _add_edge(graph, ip_node, phone_node, EDGE_LOGGED_FROM, evidence=session_id)
        if imei:
            device_node = _node_id(KIND_DEVICE, imei)
            _add_node(graph, device_node, KIND_DEVICE, label=imei, value=imei)
            _add_edge(graph, phone_node, device_node, EDGE_USED_DEVICE, evidence=session_id)
            _add_edge(graph, device_node, phone_node, EDGE_USED_DEVICE, evidence=session_id)
    return graph

def calculate_financial_metrics(graph: nx.DiGraph) -> Dict[str, Dict[str, Any]]:
    inflow, outflow = defaultdict(float), defaultdict(float)
    incoming_count, outgoing_count = defaultdict(int), defaultdict(int)
    unique_senders, unique_receivers = defaultdict(set), defaultdict(set)

    for source, target, data in graph.edges(data=True):
        if data.get("edge_kind") != EDGE_TRANSFERRED: continue
        amount = float(data.get("amount") or 0)
        outflow[source] += amount; inflow[target] += amount
        outgoing_count[source] += 1; incoming_count[target] += 1
        unique_senders[target].add(source); unique_receivers[source].add(target)

    metrics = {}
    for node in graph.nodes:
        node_in, node_out = inflow[node], outflow[node]
        metrics[node] = {
            "inflow": round(node_in, 2), "outflow": round(node_out, 2),
            "pass_through_ratio": round((node_out / node_in) if node_in > 0 else 0.0, 4),
            "incoming_count": incoming_count[node], "outgoing_count": outgoing_count[node],
            "unique_senders": len(unique_senders[node]), "unique_receivers": len(unique_receivers[node]),
        }
    return metrics

def calculate_velocity(transactions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    events = defaultdict(list)
    for txn in transactions:
        if _clean(txn.get("status")).upper() != "SUCCESS": continue
        parsed = _parse_iso(txn.get("timestamp"))
        if parsed is None: continue
        amount = float(txn.get("amount") or 0)
        sender = _node_id(KIND_ACCOUNT, _clean(txn.get("sender_account"))) if _clean(txn.get("sender_account")) else _node_id(KIND_VPA, _clean(txn.get("sender_vpa")))
        receiver = _node_id(KIND_ACCOUNT, _clean(txn.get("receiver_account"))) if _clean(txn.get("receiver_account")) else _node_id(KIND_VPA, _clean(txn.get("receiver_vpa")))
        events[sender].append((parsed, "out", amount)); events[receiver].append((parsed, "in", amount))

    velocity = {}
    for node, records in events.items():
        records.sort(key=lambda r: r[0])
        rapid, rapid_amount = 0, 0.0
        for i, (t_in, direction, _amt) in enumerate(records):
            if direction != "in": continue
            for t_out, out_direction, amount_out in records[i + 1:]:
                if out_direction != "out": continue
                delta = (t_out - t_in).total_seconds() / 60
                if delta > VELOCITY_WINDOW_MINUTES: break
                if delta >= 0: rapid += 1; rapid_amount += amount_out
        velocity[node] = {"rapid_outgoing_transfers": rapid, "rapid_outgoing_amount": round(rapid_amount, 2), "velocity_window_minutes": VELOCITY_WINDOW_MINUTES}
    return velocity

def calculate_account_risk(metrics: Dict[str, Dict[str, Any]], velocity: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, float], Dict[str, List[str]]]:
    scores, reasons = {}, {}
    for node, m in metrics.items():
        if m["incoming_count"] == 0 and m["outgoing_count"] == 0: continue
        v = velocity.get(node, {})
        score = (min(m["unique_senders"] / 3, 1.0) * 0.30 + min(m["incoming_count"] / 3, 1.0) * 0.20 + min(m["pass_through_ratio"], 1.0) * 0.30 + min(v.get("rapid_outgoing_transfers", 0) / 3, 1.0) * 0.20)
        node_reasons = []
        if m["unique_senders"] >= 2: node_reasons.append(f"Received funds from {m['unique_senders']} unique senders")
        if m["inflow"] > 0 and m["pass_through_ratio"] >= 0.8: node_reasons.append(f"High pass-through ratio ({m['pass_through_ratio']:.0%})")
        if v.get("rapid_outgoing_transfers", 0) >= 1: node_reasons.append(f"Rapid onward transfer within {v['velocity_window_minutes']} min")
        if m["incoming_count"] >= 2: node_reasons.append(f"{m['incoming_count']} incoming transactions")
        scores[node], reasons[node] = round(score, 4), node_reasons
    return scores, reasons

def detect_handler_signals(graph: nx.DiGraph, calls: List[Dict[str, Any]], metrics: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    # 1. Find "mule phones" - phones linked to accounts that send money
    mule_phones = set()
    for node, m in metrics.items():
        if m["outflow"] > 0: # This account sends money
            for neighbor in graph.neighbors(node):
                if graph.nodes[neighbor].get("kind") == KIND_PHONE:
                    mule_phones.add(graph.nodes[neighbor].get("value", ""))

    # 2. Find callers who call these mule phones
    caller_targets = defaultdict(set)
    for call in calls:
        direction = _clean(call.get("direction")).upper()
        if direction and direction != "OUT": continue
        caller, target = _clean(call.get("caller")), _clean(call.get("target_number"))
        if caller and target and caller != target: caller_targets[caller].add(target)
    
    signals = {}
    for caller, targets in caller_targets.items():
        mule_targets = [t for t in targets if t in mule_phones]
        # If they call even 1 mule, flag them! (Synthetic data might be small)
        if len(mule_targets) >= 1: 
            signals[caller] = {"distinct_call_targets": len(targets), "high_risk_targets": len(mule_targets), "sample_targets": sorted(mule_targets)[:10]}
    return signals

def calculate_network_controllers(graph: nx.DiGraph, account_risk: Dict[str, float], metrics: Dict[str, Dict[str, Any]], velocity: Dict[str, Dict[str, Any]], handler_signals: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    undirected = graph.to_undirected()
    betweenness = nx.betweenness_centrality(undirected, k=500, seed=42) if undirected.number_of_nodes() > 2000 else nx.betweenness_centrality(undirected)
    try: pagerank = nx.pagerank(graph, alpha=0.85, max_iter=200, tol=1e-4, weight=None)
    except nx.PowerIterationFailedConvergence: pagerank = {node: 1.0 / max(undirected.number_of_nodes(), 1) for node in graph.nodes}

    high_risk_accounts = {n for n, s in account_risk.items() if s >= HIGH_RISK_THRESHOLD}
    results, reasons = {}, {}

    for node in graph.nodes:
        node_data = graph.nodes[node]
        connected_high_risk, digital_links = 0, 0
        link_types = set()

        for neighbor in undirected.neighbors(node):
            if graph.nodes[neighbor].get("kind") in (KIND_ACCOUNT, KIND_VPA) and neighbor in high_risk_accounts: connected_high_risk += 1
            digital_here = False
            for (s, t) in ((node, neighbor), (neighbor, node)):
                if not graph.has_edge(s, t): continue
                edge_data = graph[s][t]
                if _is_digital_edge(edge_data):
                    digital_here = True
                    for lt in edge_data.get("link_types", []): link_types.add(lt)
            if digital_here: digital_links += 1

        handler_detail, handler_score = None, 0.0
        if node_data.get("kind") == KIND_PHONE:
            phone_value = node_data.get("value", "")
            if phone_value in handler_signals:
                handler_detail = handler_signals[phone_value]
                handler_score = min(handler_detail["high_risk_targets"] / 3, 1.0)

        mule_phone_score = 0.0
        if node_data.get("kind") in (KIND_ACCOUNT, KIND_VPA):
            phone_neighbors = sum(1 for n in undirected.neighbors(node) if graph.nodes[n].get("kind") == KIND_PHONE)
            mule_phone_score = min(phone_neighbors / 3, 1.0)

        score = (min(connected_high_risk / 3, 1.0) * 0.25 + min(digital_links / 4, 1.0) * 0.15 + min(betweenness.get(node, 0) * 10, 1.0) * 0.15 + min(pagerank.get(node, 0) * 20, 1.0) * 0.15 + handler_score * 0.15 + mule_phone_score * 0.15)
        
        node_reasons = []
        if connected_high_risk >= 2: node_reasons.append(f"Connected to {connected_high_risk} high-risk accounts")
        if digital_links >= 2: node_reasons.append(f"Linked through {digital_links} digital-footprint connections")
        if betweenness.get(node, 0) >= 0.1: node_reasons.append("Acts as a bridge between different network regions")
        if pagerank.get(node, 0) >= 0.05: node_reasons.append("High influence in the transaction network")
        if handler_detail: node_reasons.append(f"Handler signal: called {handler_detail['high_risk_targets']} high-risk mules")

        results[node] = {
            "controller_score": round(score, 4), "connected_high_risk_accounts": connected_high_risk,
            "digital_link_count": digital_links, "digital_link_types": sorted(link_types),
            "betweenness": round(betweenness.get(node, 0), 4), "pagerank": round(pagerank.get(node, 0), 4),
            "account_risk_score": account_risk.get(node, 0), "financial_metrics": metrics.get(node, {}),
            "velocity_metrics": velocity.get(node, {}), "handler_signal": handler_detail
        }
        reasons[node] = node_reasons
    return results, reasons

def detect_communities(graph: nx.DiGraph, account_risk: Dict[str, float]) -> Dict[str, Any]:
    undirected = graph.to_undirected()
    if undirected.number_of_nodes() == 0: return {"network_communities": [], "isolated_accounts": []}
    try: communities = nx.community.louvain_communities(undirected, resolution=1.0, seed=42)
    except Exception: communities = list(nx.connected_components(undirected))
    
    results, isolated = [], []
    for cluster_id, members in enumerate(communities):
        member_list = sorted(members)
        if len(member_list) <= 1: isolated.extend(member_list); continue
        scores = [account_risk.get(m, 0) for m in member_list]
        avg = sum(scores) / len(scores) if scores else 0.0
        high_risk_members = [m for m in member_list if account_risk.get(m, 0) >= HIGH_RISK_THRESHOLD]
        
        risk_level = "high" if len(high_risk_members) > 0 else "medium" if avg >= 0.20 else "low"
        
        results.append({
            "cluster_id": cluster_id, "members": member_list, "size": len(member_list),
            "average_account_risk_score": round(avg, 4),
            "high_risk_members": high_risk_members,
            "risk_level": risk_level
        })
    results.sort(key=lambda c: c["average_account_risk_score"], reverse=True)
    return {"network_communities": results, "isolated_accounts": isolated}

def detect_circular_fund_flows(graph: nx.DiGraph) -> List[Dict[str, Any]]:
    transfer_graph = _build_transfer_graph(graph)
    if transfer_graph.number_of_nodes() < 2: return []
    results = []
    try:
        cycles = itertools.islice(nx.simple_cycles(transfer_graph), 1000)
        for cycle in cycles:
            if 2 <= len(cycle) <= 8:
                total = sum(float(transfer_graph[cycle[i]][cycle[(i + 1) % len(cycle)]].get("amount") or 0) for i in range(len(cycle)) if transfer_graph.has_edge(cycle[i], cycle[(i + 1) % len(cycle)]))
                results.append({"cycle": cycle, "hops": len(cycle), "total_amount": round(total, 2), "layering_risk": "high" if len(cycle) >= 3 else "medium"})
    except Exception: pass
    results.sort(key=lambda c: c["hops"], reverse=True)
    return results[:10]

def trace_fund_flow_paths(transfer_graph: nx.DiGraph, source: str, target: str, max_hops: int = 8) -> List[Dict[str, Any]]:
    if source not in transfer_graph or target not in transfer_graph: return []
    paths = []
    try:
        for path in itertools.islice(nx.all_simple_paths(transfer_graph, source, target, cutoff=max_hops), 100):
            total_amount = sum(float(transfer_graph[path[i]][path[i + 1]].get("amount") or 0) for i in range(len(path) - 1))
            paths.append({
                "source": source, "target": target, "path": path, "transfer_hops": len(path) - 1,
                "total_amount": round(total_amount, 2),
                "hop_details": [{"from": path[i], "to": path[i + 1], "amount": float(transfer_graph[path[i]][path[i + 1]].get("amount") or 0)} for i in range(len(path) - 1)],
                "layering_risk": "high" if (len(path) - 1) >= 4 else "medium" if (len(path) - 1) >= 2 else "low"
            })
    except nx.NetworkXNoPath: return []
    paths.sort(key=lambda p: p["transfer_hops"], reverse=True)
    return paths[:10]

def identify_priority_fund_flow_paths(graph: nx.DiGraph) -> List[Dict[str, Any]]:
    transfer_graph = _build_transfer_graph(graph)
    if transfer_graph.number_of_edges() == 0: return []
    account_amounts = defaultdict(float)
    for source, _target, data in transfer_graph.edges(data=True): account_amounts[source] += float(data.get("amount") or 0)
    top = sorted(account_amounts.items(), key=lambda x: x[1], reverse=True)[:5]
    paths = []
    for source, _ in top:
        for target, _ in top:
            if source != target: paths.extend(trace_fund_flow_paths(transfer_graph, source, target, max_hops=10))
    paths.sort(key=lambda p: (p["transfer_hops"], p["total_amount"]), reverse=True)
    return paths[:10]

def export_results(graph, account_risk, account_risk_reasons, controllers, controller_reasons, communities, isolated_accounts, circular_flows, fund_paths, metadata):
    cluster_lookup = {member: community["cluster_id"] for community in communities for member in community["members"]}
    nodes = [{"id": node, "label": data.get("label", node), "kind": data.get("kind", "unknown"), "role": data.get("role", "unknown"), "value": data.get("value", ""), "account_risk_score": account_risk.get(node, 0), "account_risk_reasons": account_risk_reasons.get(node, []), "controller_score": controllers.get(node, {}).get("controller_score", 0), "controller_reasons": controller_reasons.get(node, []), "cluster_id": cluster_lookup.get(node)} for node, data in graph.nodes(data=True)]
    edges = [{"source": source, "target": target, "edge_kind": data.get("edge_kind", "LINK"), "amount": data.get("amount", 0), "transaction_count": data.get("transaction_count", 0), "link_types": data.get("link_types", []), "evidence_refs": data.get("evidence_refs", [])} for source, target, data in graph.edges(data=True)]
    with open(GRAPH_JSON_FILE, "w", encoding="utf-8") as f: json.dump({"analysis_metadata": metadata, "nodes": nodes, "edges": edges}, f, indent=2)
    with open(COMMUNITIES_FILE, "w", encoding="utf-8") as f: json.dump({"network_communities": communities, "isolated_accounts": isolated_accounts}, f, indent=2)
    ranked = sorted(controllers.items(), key=lambda item: item[1]["controller_score"], reverse=True)
    candidates = [{"entity_id": node, "label": graph.nodes[node].get("label", node), "kind": graph.nodes[node].get("kind", "unknown"), "role": graph.nodes[node].get("role", "unknown"), **values, "controller_reasons": controller_reasons.get(node, [])} for node, values in ranked]
    with open(CONTROLLERS_FILE, "w", encoding="utf-8") as f: json.dump(candidates, f, indent=2)
    with open(FUND_FLOW_FILE, "w", encoding="utf-8") as f: json.dump({"circular_fund_flows": circular_flows, "fund_flow_paths": fund_paths}, f, indent=2)

def run_network_correlation_analysis() -> Dict[str, Any]:
    print("1. Loading data...")
    data = load_all()
    transactions, calls, ip_sessions = data["transactions"], data["calls"], data["ip_sessions"]
    print(f"   Loaded {len(transactions)} transactions, {len(calls)} calls, {len(ip_sessions)} IP sessions.")
    
    graph = build_graph(transactions, calls, ip_sessions)
    metadata = {"analysis_timestamp": datetime.now(timezone.utc).isoformat(), "data_source": data_source_description(), "node_count": graph.number_of_nodes(), "edge_count": graph.number_of_edges(), "transaction_count": len(transactions), "call_count": len(calls), "ip_session_count": len(ip_sessions), "method": "Graph-based mule-mastermind correlation"}
    
    print("2. Calculating financial metrics...")
    metrics = calculate_financial_metrics(graph)
    velocity = calculate_velocity(transactions)
    account_risk, account_risk_reasons = calculate_account_risk(metrics, velocity)
    
    print("3. Detecting handler signals...")
    handler_signals = detect_handler_signals(graph, calls, metrics)
    print(f"   Found {len(handler_signals)} handler signals!")
    
    print("4. Scoring network controllers...")
    controllers, controller_reasons = calculate_network_controllers(graph, account_risk, metrics, velocity, handler_signals)
    
    print("5. Detecting communities...")
    community_result = detect_communities(graph, account_risk)
    
    print("6. Finding circular flows and fund paths...")
    circular_flows = detect_circular_fund_flows(graph)
    fund_paths = identify_priority_fund_flow_paths(graph)
    
    print("7. Exporting...")
    export_results(graph, account_risk, account_risk_reasons, controllers, controller_reasons, community_result["network_communities"], community_result["isolated_accounts"], circular_flows, fund_paths, metadata)
    
    return {"graph": graph, "account_risk_scores": account_risk, "account_risk_reasons": account_risk_reasons, "network_controller_scores": controllers, "network_controller_reasons": controller_reasons, "network_communities": community_result["network_communities"], "isolated_accounts": community_result["isolated_accounts"], "circular_fund_flows": circular_flows, "fund_paths": fund_paths, "handler_signals": handler_signals, "metadata": metadata}

if __name__ == "__main__":
    result = run_network_correlation_analysis()
    print("\n✅ Network correlation analysis completed successfully!")
    print(f"Nodes: {result['graph'].number_of_nodes()}")
    print(f"Edges: {result['graph'].number_of_edges()}")
    print(f"Communities: {len(result['network_communities'])}")
    print(f"Controllers ranked: {len(result['network_controller_scores'])}")
    print(f"Handler signals: {len(result['handler_signals'])}")
    print(f"Fund-flow paths: {len(result['fund_paths'])}")