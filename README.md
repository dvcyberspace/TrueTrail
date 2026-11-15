# TrueTrail

Mule Network Graphing and Spatiotemporal Correlation and Timeline Reconstruction
**All data in this repo is synthetic.**

## Quick start
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                                   # 26 tests
uvicorn backend.api:app --reload --port 8000          # http://localhost:8000/docs
curl -X POST localhost:8000/ingest/synthetic          # load the demo dataset
```

## Layout
```
backend/schemas.py              canonical data contract (v1.1) - shared by everyone
backend/ingestion/config.py     column maps, date formats, narration rules  <- edit to add a new source format
backend/ingestion/parsers/      upi, cdr, bank_statement, ipdr, device_forensics
backend/ingestion/pipeline.py   detect -> parse -> dedupe -> reconcile
backend/storage.py              SQLite store (rebuilt from the evidence files)
backend/api.py                  FastAPI app
backend/synthetic/generator.py  scripted scenario generator (do NOT re-run casually: xlsx hash changes)
data/synthetic/                 golden dataset + ground_truth.json (answer key) + SHA256SUMS.txt
data/canonical/                 frozen sample of the parsed output
```

## Assumptions
* Every timestamp is stored in UTC. Sources: UPI log = UTC, bank/IPDR/device dump = IST, CDR = epoch.
* RRN links a UPI log row to the matching bank-statement rows; the UPI log wins and statements go in `corroborated_by`.
* The same call appears as two CDR rows (caller side `OUT`, callee side `IN`); they are kept separate.
* Original uploaded files are the source of truth; the DB is disposable.

## Numbers on the synthetic set
5 files -> 4 schemas -> 274 transactions, 392 calls, 111 IP sessions, 25 device artifacts;
2 rejected, 3 duplicates removed, 93 cross-source matches, 14 IPDR chunks merged.
