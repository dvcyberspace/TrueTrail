import hashlib
import os
import shutil
import threading
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.ingestion import config as C
from backend.ingestion.normalizers import parse_dt, sha256_file
from backend.ingestion.pipeline import UnsupportedFile, detect_type, ingest_paths, write_outputs
from backend.schemas import SCHEMA_VERSION
from backend.storage import FILTERS, TABLES, Store

ROOT = Path(__file__).resolve().parents[1]


def _iso(v: Optional[str], name: str) -> Optional[str]:
    if not v:
        return None
    try:   # naive input is treated as UTC, to match the "everything is UTC" contract
        return parse_dt(v, assume_tz=C.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise HTTPException(400, f"'{name}' must be an ISO-8601 timestamp, got {v!r}")


def create_app(data_dir=None) -> FastAPI:
    root = Path(data_dir or os.environ.get("FORENSIC_DATA_DIR") or ROOT / "data" / "runtime")
    uploads = root / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    store = Store(root / "forensics.db")
    lock = threading.Lock()

    app = FastAPI(title="Forensic Engine - Ingestion API", version=SCHEMA_VERSION)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    def rebuild():
        files = sorted(str(p) for p in uploads.iterdir() if p.is_file())
        out = ingest_paths(files, first_seen=store.first_seen())
        store.replace_all(out)
        write_outputs(out, root / "canonical")          # JSON copies, handy for teammates / debugging
        return out

    def save_files(blobs: list) -> list:
        """blobs: [(filename, bytes)] -> save, reject unsupported. Returns per-file status."""
        results = []
        for filename, data in blobs:
            name = Path(filename or "upload").name       # strip any path (no traversal)
            sha = hashlib.sha256(data).hexdigest()
            target = uploads / name
            if target.exists() and sha256_file(str(target)) != sha:
                target = uploads / f"{target.stem}_{sha[:8]}{target.suffix}"   # same name, different bytes
            target.write_bytes(data)
            try:
                detect_type(str(target))
                results.append({"file": target.name, "status": "accepted", "sha256": sha})
            except UnsupportedFile as e:
                target.unlink(missing_ok=True)
                results.append({"file": name, "status": "skipped", "reason": str(e)})
            except Exception as e:  # noqa: BLE001  (corrupt xlsx/json etc.)
                target.unlink(missing_ok=True)
                results.append({"file": name, "status": "error", "reason": f"{type(e).__name__}: {e}"})
        return results

    def finish(results):
        out = rebuild()
        per = {p["file"]: p for p in out.summary["per_file"]}
        for r in results:
            if r["status"] == "accepted" and r["file"] in per:
                r.update({k: per[r["file"]][k] for k in ("type", "rows_in", "records", "rejected", "duplicates")})
        return {"files": results, "summary": out.summary}

    if any(p.is_file() for p in uploads.iterdir()):      # restart -> restore state from the evidence files
        rebuild()

    # ------------------------------------------------------------------ endpoints
    @app.get("/health")
    def health():
        return {"status": "ok", "schema_version": SCHEMA_VERSION, "counts": store.counts()}

    @app.post("/ingest")
    async def ingest(files: List[UploadFile] = File(...)):
        blobs = [(f.filename, await f.read()) for f in files]
        with lock:
            return finish(save_files(blobs))

    @app.post("/ingest/synthetic")
    def ingest_synthetic():
        src = ROOT / "data" / "synthetic"
        if not src.exists():
            raise HTTPException(404, "data/synthetic not found - run backend/synthetic/generator.py")
        blobs = [(p.name, p.read_bytes()) for p in sorted(src.iterdir()) if p.is_file() and p.name not in C.IGNORE_FILES]
        with lock:
            return finish(save_files(blobs))

    @app.get("/records/{rtype}")
    def records(rtype: str, request: Request, since: Optional[str] = None, until: Optional[str] = None,
                limit: int = Query(1000, ge=1, le=50000), offset: int = Query(0, ge=0)):
        if rtype not in TABLES:
            raise HTTPException(404, f"unknown type {rtype!r}; use one of {list(TABLES)}")
        allowed = FILTERS[rtype]
        reserved = {"since", "until", "limit", "offset"}
        params = {k: v for k, v in request.query_params.items() if k not in reserved}
        bad = [k for k in params if k not in allowed]
        if bad:
            raise HTTPException(400, f"unsupported filter(s) {bad}; allowed: {sorted(allowed)} + since, until, limit, offset")
        total, items = store.query(rtype, params, _iso(since, "since"), _iso(until, "until"), limit, offset)
        return {"type": rtype, "schema_version": SCHEMA_VERSION, "total": total, "limit": limit,
                "offset": offset, "items": items}

    @app.get("/evidence")
    def evidence():
        return {"items": store.evidence()}

    @app.get("/evidence/{evidence_id}")
    def evidence_one(evidence_id: str):
        ev = store.evidence(evidence_id)
        if not ev:
            raise HTTPException(404, "evidence not found")
        return ev

    @app.get("/evidence/{evidence_id}/verify")
    def verify(evidence_id: str):
        ev = store.evidence(evidence_id)
        if not ev:
            raise HTTPException(404, "evidence not found")
        p = uploads / ev["filename"]
        if not p.exists():
            return {"evidence_id": evidence_id, "filename": ev["filename"], "match": False, "reason": "stored file missing"}
        now = sha256_file(str(p))
        return {"evidence_id": evidence_id, "filename": ev["filename"], "expected_sha256": ev["sha256"],
                "current_sha256": now, "match": now == ev["sha256"]}

    @app.get("/rejected")
    def rejected(limit: int = Query(1000, ge=1, le=50000), offset: int = Query(0, ge=0)):
        total, items = store.rejected(limit, offset)
        return {"total": total, "items": items}

    @app.get("/ingestion/summary")
    def summary():
        return store.summary()

    @app.post("/reset")
    def reset():
        with lock:
            shutil.rmtree(uploads, ignore_errors=True)
            uploads.mkdir(parents=True, exist_ok=True)
            store.reset()
        return {"status": "reset"}

    return app


app = create_app()
