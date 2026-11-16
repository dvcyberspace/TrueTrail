import hashlib, json, sqlite3
from datetime import datetime, timezone

DB = "audit.db"
GENESIS = "0" * 64

def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()

def _conn():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, actor TEXT, action TEXT, file_name TEXT,
        file_hash TEXT, prev_hash TEXT, entry_hash TEXT)""")
    return c

def _entry_hash(ts, actor, action, file_name, file_hash, prev):
    payload = json.dumps([ts, actor, action, file_name, file_hash, prev])
    return hashlib.sha256(payload.encode()).hexdigest()

def log_event(actor, action, file_name, file_hash):
    c = _conn()
    row = c.execute("SELECT entry_hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    prev = row[0] if row else GENESIS
    ts = datetime.now(timezone.utc).isoformat()
    eh = _entry_hash(ts, actor, action, file_name, file_hash, prev)
    c.execute("INSERT INTO audit(ts,actor,action,file_name,file_hash,prev_hash,entry_hash) "
              "VALUES (?,?,?,?,?,?,?)", (ts, actor, action, file_name, file_hash, prev, eh))
    c.commit(); c.close()
    return eh

def verify_chain():
    c = _conn()
    rows = c.execute("SELECT ts,actor,action,file_name,file_hash,prev_hash,entry_hash "
                     "FROM audit ORDER BY id").fetchall()
    c.close()
    prev = GENESIS
    for i, (ts, actor, action, fn, fh, p, eh) in enumerate(rows):
        if p != prev or _entry_hash(ts, actor, action, fn, fh, p) != eh:
            return {"valid": False, "broken_at_entry": i + 1}
        prev = eh
    return {"valid": True, "entries": len(rows)}