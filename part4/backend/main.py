import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from integrity import sha256_file, log_event, verify_chain, _conn
from report import build_pack

P1 = "http://127.0.0.1:8000"

app = FastAPI(title="Part 4 - Evidence Integrity")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def p1(path):
    try:
        r = requests.get(P1 + path, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(502, f"Part 1 API error: {e}")


def registered():
    rows = _conn().execute(
        "SELECT file_name, file_hash FROM audit WHERE action='REGISTER' ORDER BY id").fetchall()
    return {n: h for n, h in rows}


@app.post("/sync")
def sync():
    reg = registered()
    new = []
    for e in p1("/evidence")["items"]:
        if e["filename"] not in reg:
            log_event("system", "REGISTER", e["filename"], e["sha256"])
            new.append(e["filename"])
    return {"registered": new}


@app.get("/evidence")
def evidence():
    reg = registered()
    items = p1("/evidence")["items"]
    for e in items:
        e["registered_sha256"] = reg.get(e["filename"])
    return {"items": items}


@app.get("/evidence/{evidence_id}/verify")
def verify(evidence_id: str):
    v = p1(f"/evidence/{evidence_id}/verify")
    reg = registered().get(v["filename"])
    cur = v.get("current_sha256")
    ok = reg is not None and cur == reg
    log_event("investigator", "VERIFY_OK" if ok else "VERIFY_FAIL", v["filename"], cur or "-")
    return {**v, "registered_sha256": reg, "match": ok}


@app.get("/audit")
def audit():
    rows = _conn().execute("SELECT * FROM audit ORDER BY id").fetchall()
    keys = ["id", "ts", "actor", "action", "file", "file_hash", "prev_hash", "entry_hash"]
    return [dict(zip(keys, r)) for r in rows]


@app.get("/audit/verify")
def audit_verify():
    return verify_chain()


@app.get("/report")
def report(case_id: str = "CASE-001"):
    sync()
    build_pack("pack.pdf", {"case_id": case_id}, p1("/evidence")["items"], audit(), verify_chain())
    log_event("investigator", "REPORT", "pack.pdf", sha256_file("pack.pdf"))
    return FileResponse("pack.pdf", media_type="application/pdf",
                        filename=f"{case_id}_evidence_pack.pdf")

from fastapi.responses import FileResponse
from report import generate_report

@app.post("/report")
def create_report(file_name: str, file_hash: str, case_id: str):
    path = generate_report(file_name, file_hash, case_id, "Insp. Rajesh Kumar")
    return FileResponse(path, media_type="application/pdf", filename=f"BSA_{case_id}.pdf")