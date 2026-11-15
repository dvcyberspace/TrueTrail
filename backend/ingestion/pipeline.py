import csv
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from backend.ingestion import config as C
from backend.ingestion.normalizers import sha256_file
from backend.ingestion.parsers.base import ParseResult, missing_required
from backend.ingestion.parsers.bank_statement import parse_bank_statement
from backend.ingestion.parsers.cdr import parse_cdr
from backend.ingestion.parsers.device_forensics import parse_device_dump
from backend.ingestion.parsers.ipdr import merge_sessions, parse_ipdr
from backend.ingestion.parsers.upi import parse_upi
from backend.schemas import EvidenceItem, RejectedRow, SCHEMA_VERSION

PARSERS = {"upi": parse_upi, "cdr": parse_cdr, "bank_statement": parse_bank_statement,
           "ipdr": parse_ipdr, "device": parse_device_dump}
CSV_SPECS = {"upi": C.UPI, "cdr": C.CDR, "ipdr": C.IPDR}


class UnsupportedFile(Exception):
    pass


def detect_type(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if p.name in C.IGNORE_FILES:
        raise UnsupportedFile("ignored (not evidence)")
    if ext in (".xlsx", ".xlsm"):
        return "bank_statement"
    if ext == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            header = next(csv.reader(f), [])
        for t, spec in CSV_SPECS.items():
            if not missing_required(header, spec):
                return t
        raise UnsupportedFile(f"CSV header matches no known source: {header[:6]}...")
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        if isinstance(doc, dict) and "report_header" in doc:
            return "device"
        raise UnsupportedFile("JSON is not a forensic extraction (no report_header)")
    raise UnsupportedFile(f"unsupported extension {ext}")


def reconcile_transactions(txns: list) -> tuple:
    """One real-world payment can appear in the UPI log AND in sender's AND receiver's statements.
    Collapse by RRN: UPI log wins; the other files are recorded in `corroborated_by` (useful for the
    court pack: independent sources agree)."""
    by_rrn, out, merged = {}, [], 0
    for t in sorted(txns, key=lambda t: t.source_type != "UPI_LOG"):      # stable: UPI log first
        if t.rrn and t.rrn in by_rrn:
            p = by_rrn[t.rrn]
            if t.source_file not in p.corroborated_by:
                p.corroborated_by.append(t.source_file)
            p.narration = p.narration or t.narration
            p.balance_after = p.balance_after if p.balance_after is not None else t.balance_after
            merged += 1
            continue
        if t.rrn:
            by_rrn[t.rrn] = t
        out.append(t)
    out.sort(key=lambda t: t.timestamp)
    return out, merged


@dataclass
class IngestionOutput:
    evidence: list = field(default_factory=list)
    transactions: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    ip_sessions: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def ingest_file(path: str, first_seen: dict | None = None) -> tuple:
    """first_seen: {sha256: datetime} so re-processing a file keeps its ORIGINAL ingestion time
    (chain of custody). evidence_id is deterministic (uuid5 of the SHA-256): same bytes -> same ID."""
    etype = detect_type(path)
    res: ParseResult = PARSERS[etype](path)
    sha = sha256_file(path)
    ev = EvidenceItem(evidence_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "sha256:" + sha)), filename=Path(path).name,
                      sha256=sha, evidence_type=etype,
                      ingested_at=(first_seen or {}).get(sha) or datetime.now(timezone.utc),
                      record_count=len(res.records),
                      rows_in=res.rows_in, rejected_count=len(res.rejected), duplicate_count=res.duplicates)
    return ev, res


def ingest_paths(paths: list, merge_ipdr: bool = True, first_seen: dict | None = None) -> IngestionOutput:
    out = IngestionOutput()
    per_file, all_txn, raw_ip = [], [], []
    for p in paths:
        try:
            ev, res = ingest_file(p, first_seen)
        except UnsupportedFile as e:
            out.skipped.append({"file": Path(p).name, "reason": str(e)})
            continue
        out.evidence.append(ev)
        out.rejected += res.rejected
        per_file.append({"file": ev.filename, "type": ev.evidence_type, "rows_in": res.rows_in,
                         "records": len(res.records), "rejected": len(res.rejected), "duplicates": res.duplicates})
        t = ev.evidence_type
        if t in ("upi", "bank_statement"):
            all_txn += res.records
        elif t == "cdr":
            out.calls += res.records
        elif t == "ipdr":
            raw_ip += res.records
        elif t == "device":
            out.artifacts += res.records

    out.transactions, xmatched = reconcile_transactions(all_txn)
    out.ip_sessions = merge_sessions(raw_ip) if merge_ipdr else raw_ip
    out.summary = {
        "schema_version": SCHEMA_VERSION,
        "files_ingested": len(out.evidence), "files_skipped": out.skipped,
        "schemas_produced": sum(bool(x) for x in (out.transactions, out.calls, out.ip_sessions, out.artifacts)),
        "per_file": per_file,
        "totals": {"transactions": len(out.transactions), "calls": len(out.calls), "ip_sessions": len(out.ip_sessions),
                   "device_artifacts": len(out.artifacts), "rejected_rows": len(out.rejected),
                   "duplicates_removed": sum(f["duplicates"] for f in per_file),
                   "cross_source_txn_matches": xmatched,
                   "ipdr_chunks_merged": len(raw_ip) - len(out.ip_sessions) if merge_ipdr else 0},
        "all_timestamps": "UTC",
    }
    return out


def write_outputs(out: IngestionOutput, outdir: str):
    d = Path(outdir)
    d.mkdir(parents=True, exist_ok=True)
    dump = lambda name, recs: (d / name).write_text(  # noqa: E731
        json.dumps([r.model_dump(mode="json") for r in recs], indent=1), encoding="utf-8")
    dump("transactions.json", out.transactions)
    dump("calls.json", out.calls)
    dump("ip_sessions.json", out.ip_sessions)
    dump("device_artifacts.json", out.artifacts)
    dump("evidence_items.json", out.evidence)
    (d / "ingestion_summary.json").write_text(json.dumps(out.summary, indent=2), encoding="utf-8")
    with open(d / "rejected_rows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_file", "source_row", "reason", "raw"])
        for r in out.rejected:
            w.writerow([r.source_file, r.source_row, r.reason, json.dumps(r.raw, default=str)])
