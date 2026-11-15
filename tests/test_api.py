from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app

SYN = Path(__file__).resolve().parents[1] / "data" / "synthetic"
pytestmark = pytest.mark.skipif(not (SYN / "upi_logs.csv").exists(), reason="synthetic data not generated")


@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(tmp_path))


def test_upload_filter_evidence_verify_and_idempotence(client):
    files = [("files", (p.name, p.read_bytes())) for p in sorted(SYN.iterdir()) if p.is_file()]
    r = client.post("/ingest", files=files).json()
    assert r["summary"]["totals"]["transactions"] == 274
    assert {f["status"] for f in r["files"]} == {"accepted", "skipped"}

    # re-upload the same files -> identical state (idempotent)
    r2 = client.post("/ingest", files=files).json()
    assert r2["summary"]["totals"] == r["summary"]["totals"]

    d = client.get("/records/calls", params={"call_type": "VIDEO", "direction": "IN"}).json()
    assert d["total"] >= 1 and d["items"][0]["duration_sec"] == 12420
    assert client.get("/records/transactions", params={"since": "2026-03-14T05:00:00Z", "until": "2026-03-14T08:30:00Z"}).json()["total"] > 21
    assert client.get("/records/transactions", params={"bogus": "x"}).status_code == 400
    assert client.get("/records/nothing").status_code == 404

    ev = client.get("/evidence").json()["items"]
    assert len(ev) == 5 and all(len(e["sha256"]) == 64 for e in ev)
    assert client.get(f"/evidence/{ev[0]['evidence_id']}/verify").json()["match"] is True
    assert client.get("/rejected").json()["total"] == 2


def test_unsupported_file_is_skipped_not_stored(client):
    r = client.post("/ingest", files=[("files", ("notes.txt", b"hello"))]).json()
    assert r["files"][0]["status"] == "skipped"
    assert client.get("/evidence").json()["items"] == []


def test_state_survives_restart(tmp_path):
    c1 = TestClient(create_app(tmp_path))
    assert c1.post("/ingest/synthetic").status_code == 200
    c2 = TestClient(create_app(tmp_path))                     # new process, same data dir
    assert c2.get("/health").json()["counts"]["transactions"] == 274
