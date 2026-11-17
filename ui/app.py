"""Fraud Link Analysis MVP — Streamlit UI."""
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st
from pyvis.network import Network

st.set_page_config(page_title="Fraud Link Analysis MVP", layout="wide")

st.title("Fraud Link Analysis MVP")
st.caption("Synthetic data. The system suggests; the investigator decides.")
st.warning("All data shown is fully synthetic and generated for demonstration purposes.")

DATA_DIR = "data"
OUTPUT_DIR = "outputs"
AUDIT_FILE = os.path.join(OUTPUT_DIR, "audit_log.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------------------------------------------- Sidebar --
st.sidebar.title("Case controls")
role = st.sidebar.selectbox("Select role", ["Investigator", "Supervisor", "Auditor"])

if st.sidebar.button("Load demo case"):
    st.session_state["loaded"] = True
    st.sidebar.success("Demo case loaded. You can now review transactions and analyze the network.")

uploaded_files = st.sidebar.file_uploader("Upload CSV files", accept_multiple_files=True, type=["csv"])

def load_ui_data():
    if uploaded_files:
        data = {}
        for f in uploaded_files:
            name = f.name.lower()
            if "entities" in name: data["entities"] = pd.read_csv(f)
            elif "transactions" in name: data["transactions"] = pd.read_csv(f)
            elif "events" in name: data["events"] = pd.read_csv(f)
            elif "links" in name: data["links"] = pd.read_csv(f)
        return data
    if st.session_state.get("loaded"):
        out = {}
        for key, fname in [("entities", "entities.csv"), ("transactions", "transactions.csv"), ("events", "events.csv"), ("links", "links.csv")]:
            path = os.path.join(DATA_DIR, fname)
            out[key] = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
        return out
    return None

data = load_ui_data()
page = st.sidebar.radio("Navigation", ["Transaction Review", "Network Correlation Analysis"], key="main_navigation")

if data is None:
    data = {"entities": pd.DataFrame(), "transactions": pd.DataFrame(), "events": pd.DataFrame(), "links": pd.DataFrame()}

# ================================================================ Page 1 ======
def render_transaction_review_page():
    entities, transactions, events, links = data["entities"], data["transactions"], data["events"], data["links"]
    if entities.empty or transactions.empty:
        st.info("Click **Load demo case** in the left sidebar or upload the required CSV files.")
        return

    # FIX: Force all account numbers to be strings and strip spaces
    entities["entity_id"] = entities["entity_id"].astype(str).str.strip()
    transactions["to_acct"] = transactions["to_acct"].astype(str).str.strip()
    transactions["from_acct"] = transactions["from_acct"].astype(str).str.strip()

    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Network", "Timeline", "Evidence"])

    with tab1:
        st.subheader("Case overview")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Entities", len(entities)); col2.metric("Transactions", len(transactions))
        col3.metric("Events", len(events)); col4.metric("Evidence links", len(links))

        st.subheader("Suspicious account leads (Legacy CSV Data)")
        results = []
        for _, account in entities[entities["type"] == "account"].iterrows():
            acc_id = str(account["entity_id"])
            
            # Now this will match perfectly
            incoming = transactions[transactions["to_acct"] == acc_id]
            outgoing = transactions[transactions["from_acct"] == acc_id]
            
            inflow, outflow = incoming["amount"].sum(), outgoing["amount"].sum()
            unique_senders = incoming["from_acct"].nunique()
            
            # FIX: Adjusted logic so it calculates something even if they just send money
            score = min(unique_senders / 2, 1) * 0.40 + min(outflow / inflow if inflow else 0, 1) * 0.30 + min(len(incoming) / 2, 1) * 0.30
            
            # If they are sending a lot of money but receiving nothing, they are still suspicious
            if inflow == 0 and outflow > 0:
                score = 0.50 

            reasons = []
            if unique_senders > 0: reasons.append(f"Received from {unique_senders} sender(s)")
            if inflow > 0: reasons.append(f"Pass-through ratio: {outflow / inflow:.0%}")
            if inflow == 0 and outflow > 0: reasons.append("Pure Sender (No incoming funds)")
            if not reasons: reasons.append("No suspicious activity detected")

            results.append({
                "Account": account["label"], 
                "Mule score": round(score, 2), 
                "Money received": round(inflow, 2), 
                "Money sent": round(outflow, 2), 
                "Reasons": "; ".join(reasons)
            })
            
        scores = pd.DataFrame(results).sort_values("Mule score", ascending=False)
        st.dataframe(scores, use_container_width=True)

    with tab2:
        st.subheader("Transaction network (Legacy CSV)")
        st.info("For speed, the graph only displays up to 100 nodes.")
        graph = Network(height="600px", directed=True, bgcolor="#ffffff")
        graph.barnes_hut()
        
        existing_nodes = set()
        for _, txn in transactions.head(100).iterrows():
            source, target = str(txn["from_acct"]), str(txn["to_acct"])
            if source not in existing_nodes: graph.add_node(source, label=source); existing_nodes.add(source)
            if target not in existing_nodes: graph.add_node(target, label=target); existing_nodes.add(target)
            graph.add_edge(source, target, title=f"Amount: INR {txn['amount']}", color="#FF5630")

        network_html = os.path.join(OUTPUT_DIR, "legacy_network.html")
        graph.save_graph(network_html)
        with open(network_html, "r", encoding="utf-8") as f: html = f.read()
        st.components.v1.html(html, height=620)

    with tab3:
        st.subheader("Event timeline")
        timeline = events.copy().head(200)
        timeline["timestamp"] = pd.to_datetime(timeline["timestamp"], errors="coerce")
        timeline = timeline.dropna(subset=["timestamp"]).sort_values("timestamp")
        if not timeline.empty:
            fig = px.scatter(timeline, x="timestamp", y="entity_id", color="type", title="Events over time")
            st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("Evidence and decision")
        selected = st.selectbox("Select entity", entities["entity_id"].tolist(), format_func=lambda eid: entities[entities["entity_id"] == eid]["label"].iloc[0])
        
        st.write("### Events")
        st.dataframe(events[events["entity_id"] == selected].head(20), use_container_width=True)
        
        if "audit_log" not in st.session_state: st.session_state["audit_log"] = []

        def _audit(action: str):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state["audit_log"].append({"time": ts, "user": role, "action": action, "entity": selected})
            write_header = not os.path.exists(AUDIT_FILE) or os.path.getsize(AUDIT_FILE) == 0
            with open(AUDIT_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header: writer.writerow(["time", "user", "action", "entity"])
                writer.writerow([ts, role, action, selected])

        st.write("### Decision")
        accept_col, reject_col = st.columns(2)
        if accept_col.button("Accept lead"):
            _audit("Accepted lead")
            st.success("Lead accepted and audit entry recorded.")
        if reject_col.button("Reject lead"):
            _audit("Rejected lead")
            st.warning("Lead rejected and audit entry recorded.")

        if st.session_state["audit_log"]:
            st.write("### Audit log (Session)")
            st.dataframe(pd.DataFrame(st.session_state["audit_log"]), use_container_width=True)
# ================================================================ Page 2 ======
def _lazy_run_network_engine():
    try:
        from engine.network_correlation import run_network_correlation_analysis
    except Exception as error:
        st.error("Failed to import network engine."); st.exception(error); return
    with st.spinner("Analyzing transaction network... This may take a few seconds."):
        try:
            result = run_network_correlation_analysis()
            st.cache_data.clear() 
        except Exception as error:
            st.error("Analysis failed."); st.exception(error); return
    st.success("Network correlation analysis completed!")
    st.rerun()

@st.cache_data(show_spinner=False)
def load_json_safe(path):
    if not os.path.exists(path): return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def render_network_correlation_page():
    st.title("Network Correlation Analysis (TrueTrail Data)")
    st.write("Analyze transaction and digital-footprint connections to identify high-risk communities and masterminds.")

    if st.button("Run network correlation analysis", type="primary"):
        _lazy_run_network_engine()

    st.divider()

    graph_file = os.path.join(OUTPUT_DIR, "network_graph.json")
    graph_data = load_json_safe(graph_file)

    if not graph_data:
        st.warning("⚠️ Click **Run network correlation analysis** to generate the graph.")
        return

    # Create Tabs for Graph and Tables
    tab_graph, tab_tables = st.tabs(["🕸️ Visual Network Graph", "📊 Data Tables (Masterminds & Trails)"])

    # ================= TAB 1: VISUAL GRAPH =================
    with tab_graph:
        st.subheader("Network Graph (TrueTrail)")
        st.info("Showing top 150 connections. Hover over nodes to see their risk scores. Red nodes are Accounts, Blue are Phones, Yellow are Devices.")
        
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        # 1. Sort nodes by controller score to show the most important ones
        nodes.sort(key=lambda x: x.get("controller_score", 0), reverse=True)
        top_nodes = nodes[:100] # Limit to 100 nodes to avoid browser lag
        node_ids = {n["id"] for n in top_nodes}

        net = Network(height="700px", width="100%", bgcolor="#222222", font_color="white", directed=True)
        
        for n in top_nodes:
            kind = n.get("kind", "unknown")
            score = n.get("controller_score", 0)
            risk = n.get("account_risk_score", 0)
            
            # Color mapping
            color = "#4C9AFF" # default blue
            if kind == "account": color = "#FF5630" # red
            elif kind == "phone": color = "#36B37E" # green
            elif kind == "device": color = "#FFAB00" # yellow
            elif kind == "ip_address": color = "#6554C0" # purple

            # Make masterminds bigger
            size = 15 + (score * 30)
            
            title = f"Label: {n['label']}<br>Kind: {kind}<br>Controller Score: {score}<br>Risk Score: {risk}"
            net.add_node(n["id"], label=n["label"], color=color, size=size, title=title)

        # Filter edges to only those between top nodes
        for e in edges:
            if e["source"] in node_ids and e["target"] in node_ids:
                kind = e.get("edge_kind", "LINK")
                color = "#FF5630" if kind == "TRANSFERRED" else "#555555" # Red for money, Grey for digital
                title = f"Type: {kind}"
                if kind == "TRANSFERRED": title += f"<br>Amount: {e.get('amount')}"
                net.add_edge(e["source"], e["target"], title=title, color=color, arrows="to")

        net.set_options("""
        var options = {
          "physics": { "barnesHut": { "gravitationalConstant": -8000, "springLength": 200 } }
        }
        """)
        
        html_file = os.path.join(OUTPUT_DIR, "true_trail_network.html")
        net.save_graph(html_file)
        with open(html_file, "r", encoding="utf-8") as f:
            st.components.v1.html(f.read(), height=720)

    # ================= TAB 2: DATA TABLES =================
    with tab_tables:
        # ---- Communities ----
        st.subheader("1. Account Communities (Clusters)")
        communities_file = os.path.join(OUTPUT_DIR, "network_communities.json")
        payload = load_json_safe(communities_file)
        
        if payload:
            communities = payload.get("network_communities", []) if isinstance(payload, dict) else payload
            valid_communities = [c for c in communities if isinstance(c, dict) and c.get("size", 0) > 1]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Connected communities", len(valid_communities))
            c2.metric("Total communities", len(communities))
            c3.metric("High-risk communities", sum(1 for c in communities if isinstance(c, dict) and c.get("risk_level") == "high"))

            if valid_communities:
                rows = []
                for c in valid_communities:
                    rows.append({
                        "Cluster ID": c.get("cluster_id"), "Size": c.get("size"),
                        "Risk Level": c.get("risk_level").upper(), "Avg Risk Score": c.get("average_account_risk_score"),
                        "Sample Members": ", ".join(c.get("members", [])[:3]) + "..."
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.warning("Run the analysis to see communities.")

        st.divider()

        # ---- Controllers ----
        st.subheader("2. Mastermind & Controller Candidates")
        controllers_file = os.path.join(OUTPUT_DIR, "network_controller_candidates.json")
        controllers = load_json_safe(controllers_file)

        if controllers and isinstance(controllers, list) and len(controllers) > 0:
            rows = []
            for c in controllers[:10]:
                reasons = "; ".join(c.get("controller_reasons", []))
                handler = "YES" if c.get("handler_signal") else "No"
                rows.append({
                    "Entity ID": c.get("entity_id"), "Kind": c.get("kind"),
                    "Controller Score": c.get("controller_score"), 
                    "High-risk Connections": c.get("connected_high_risk_accounts"),
                    "Handler Signal": handler,
                    "Why? (Reasons)": reasons[:80] + ("..." if len(reasons) > 80 else "")
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.info("No controllers ranked.")
        else:
            st.warning("Run the analysis to see controllers.")

        st.divider()

        # ---- Fund flow ----
        st.subheader("3. Money Trail (Fund-flow paths)")
        fund_flow_file = os.path.join(OUTPUT_DIR, "fund_flow_analysis.json")
        fund = load_json_safe(fund_flow_file)

        if fund:
            paths = fund.get("fund_flow_paths", [])
            c1, c2 = st.columns(2)
            c1.metric("Multi-hop paths found", len(paths))
            c2.metric("Circular (laundering) loops", len(fund.get("circular_fund_flows", [])))

            if paths:
                rows = [{"Source": p["source"], "Target": p["target"], "Hops": p["transfer_hops"], "Amount": p["total_amount"], "Risk": p["layering_risk"].upper()} for p in paths[:10]]
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.warning("Run the analysis to see fund flows.")

# ----------------------------------------------------------------- Routing --
if page == "Transaction Review":
    render_transaction_review_page()
elif page == "Network Correlation Analysis":
    render_network_correlation_page()