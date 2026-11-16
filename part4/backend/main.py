import os, shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from integrity import sha256_file, log_event, verify_chain, _conn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
os.makedirs("evidence", exist_ok=True)

@app.post("/evidence/upload")
async def upload(file: UploadFile = File(...), actor: str = "investigator"):
    path = f"evidence/{file.filename}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    h = sha256_file(path)
    log_event(actor, "INGEST", file.filename, h)
    return {"file": file.filename, "sha256": h}

@app.get("/evidence/{name}/verify")
def verify(name: str):
    h = sha256_file(f"evidence/{name}")
    row = _conn().execute("SELECT file_hash FROM audit WHERE file_name=? AND action='INGEST' "
                          "ORDER BY id LIMIT 1", (name,)).fetchone()
    log_event("investigator", "VERIFY", name, h)
    return {"file": name, "current": h, "original": row[0], "match": h == row[0]}

@app.get("/audit")
def audit():
    rows = _conn().execute("SELECT * FROM audit ORDER BY id").fetchall()
    return [dict(zip(["id","ts","actor","action","file","file_hash","prev_hash","entry_hash"], r)) for r in rows]

@app.get("/audit/verify")
def audit_verify():
    return verify_chain()