import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# type -> (table, id field, time field)
TABLES = {
    "transactions": ("transactions", "txn_id", "timestamp"),
    "calls": ("calls", "record_id", "start_time"),
    "ip_sessions": ("ip_sessions", "record_id", "start_time"),
    "device_artifacts": ("device_artifacts", "artifact_id", "timestamp"),
}
# query-param -> JSON fields it matches (OR). Whitelist = no SQL injection, and it documents the API.
FILTERS = {
    "transactions": {"account": ["sender_account", "receiver_account"], "vpa": ["sender_vpa", "receiver_vpa"],
                     "device_id": ["device_id"], "ip": ["ip_address"], "channel": ["channel"],
                     "source_type": ["source_type"], "rrn": ["rrn"], "status": ["status"]},
    "calls": {"number": ["caller", "callee", "target_number"], "imei": ["imei"], "direction": ["direction"],
              "call_type": ["call_type"], "cell": ["cell_tower_id", "last_cell_id"]},
    "ip_sessions": {"msisdn": ["msisdn"], "ip": ["src_ip", "dst_ip"], "imei": ["imei"], "app_hint": ["app_hint"]},
    "device_artifacts": {"artifact_type": ["artifact_type"], "app": ["app"], "counterparty": ["counterparty"],
                         "device_id": ["device_id"]},
}


class Store:
    def __init__(self, db_path):
        self.path = str(db_path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            for t, _, _ in TABLES.values():
                c.execute(f"CREATE TABLE IF NOT EXISTS {t} (id TEXT PRIMARY KEY, ts TEXT, doc TEXT NOT NULL)")
                c.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_ts ON {t}(ts)")
            c.execute("CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, sha256 TEXT, doc TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS rejected (n INTEGER PRIMARY KEY AUTOINCREMENT, doc TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    # ------------------------------------------------------------------ write
    def replace_all(self, out):
        """Atomically replace everything with a fresh IngestionOutput."""
        dump = lambda r: json.dumps(r.model_dump(mode="json"), default=str)  # noqa: E731
        with self._lock, self._conn() as c:
            for rtype, recs in (("transactions", out.transactions), ("calls", out.calls),
                                ("ip_sessions", out.ip_sessions), ("device_artifacts", out.artifacts)):
                table, idf, tsf = TABLES[rtype]
                c.execute(f"DELETE FROM {table}")
                rows = []
                for r in recs:
                    d = r.model_dump(mode="json")
                    rows.append((d[idf], d.get(tsf), json.dumps(d, default=str)))
                c.executemany(f"INSERT OR REPLACE INTO {table} VALUES (?,?,?)", rows)
            c.execute("DELETE FROM evidence")
            c.executemany("INSERT INTO evidence VALUES (?,?,?)",
                          [(e.evidence_id, e.sha256, dump(e)) for e in out.evidence])
            c.execute("DELETE FROM rejected")
            c.executemany("INSERT INTO rejected(doc) VALUES (?)", [(dump(r),) for r in out.rejected])
            c.execute("INSERT OR REPLACE INTO meta VALUES ('summary', ?)", (json.dumps(out.summary, default=str),))

    def reset(self):
        with self._lock, self._conn() as c:
            for t, _, _ in TABLES.values():
                c.execute(f"DELETE FROM {t}")
            for t in ("evidence", "rejected", "meta"):
                c.execute(f"DELETE FROM {t}")

    # ------------------------------------------------------------------ read
    def query(self, rtype: str, params: dict, since: Optional[str], until: Optional[str],
              limit: int, offset: int) -> tuple:
        table, _, _ = TABLES[rtype]
        where, args = [], []
        for p, val in params.items():
            fields = FILTERS[rtype][p]
            where.append("(" + " OR ".join(f"json_extract(doc,'$.{f}') = ?" for f in fields) + ")")
            args += [val] * len(fields)
        if since:
            where.append("ts >= ?"); args.append(since)
        if until:
            where.append("ts <= ?"); args.append(until)
        w = (" WHERE " + " AND ".join(where)) if where else ""
        with self._conn() as c:
            total = c.execute(f"SELECT COUNT(*) FROM {table}{w}", args).fetchone()[0]
            rows = c.execute(f"SELECT doc FROM {table}{w} ORDER BY ts, id LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
        return total, [json.loads(r["doc"]) for r in rows]

    def counts(self) -> dict:
        with self._conn() as c:
            return {k: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for k, (t, _, _) in TABLES.items()}

    def evidence(self, evidence_id: Optional[str] = None):
        with self._conn() as c:
            if evidence_id:
                r = c.execute("SELECT doc FROM evidence WHERE id=?", (evidence_id,)).fetchone()
                return json.loads(r["doc"]) if r else None
            return [json.loads(r["doc"]) for r in c.execute("SELECT doc FROM evidence ORDER BY json_extract(doc,'$.filename')")]

    def first_seen(self) -> dict:
        """{sha256: datetime} - keeps the original ingestion time across rebuilds."""
        with self._conn() as c:
            return {r["sha256"]: datetime.fromisoformat(json.loads(r["doc"])["ingested_at"].replace("Z", "+00:00"))
                    for r in c.execute("SELECT sha256, doc FROM evidence")}

    def rejected(self, limit: int, offset: int) -> tuple:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM rejected").fetchone()[0]
            rows = c.execute("SELECT doc FROM rejected ORDER BY n LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return total, [json.loads(r["doc"]) for r in rows]

    def summary(self) -> dict:
        with self._conn() as c:
            r = c.execute("SELECT v FROM meta WHERE k='summary'").fetchone()
        return json.loads(r["v"]) if r else {}
