# report/audit.py
"""Chain-of-custody: SHA-256 hashing + append-only audit log."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = "data"                
AUDIT_LOG = "demo/audit_log.jsonl"        


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_all_evidence() -> dict[str, str]:
    """Hash both raw + standardized. Raw = 'as uploaded', std = 'as analysed'."""
    out = {}
    for d in ("evidence_data", "data"):
        p = Path(d)
        if p.exists():
            for f in sorted(p.glob("*.*")):
                out[f"{d}/{f.name}"] = sha256_file(str(f))
    return out


def log_event(user: str, action: str, target: str, extra: dict | None = None) -> dict:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "action": action,       # upload | view | accept | reject | annotate | export
        "target": target,       # filename or lead_id
        "extra": extra or {},
    }
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_audit_log() -> list[dict]:
    if not os.path.exists(AUDIT_LOG):
        return []
    with open(AUDIT_LOG) as f:
        return [json.loads(line) for line in f if line.strip()]