"""Parser tests against the frozen synthetic dataset (data/synthetic)."""
import json
from pathlib import Path

import pytest

from backend.ingestion.pipeline import ingest_paths

SYN = Path(__file__).resolve().parents[1] / "data" / "synthetic"
pytestmark = pytest.mark.skipif(not (SYN / "upi_logs.csv").exists(), reason="synthetic data not generated")


@pytest.fixture(scope="module")
def out():
    return ingest_paths([str(p) for p in sorted(SYN.iterdir()) if p.is_file()])


def per_file(out, name):
    return next(f for f in out.summary["per_file"] if f["file"] == name)


def test_all_five_sources_ingested_and_ignored_files_skipped(out):
    assert out.summary["files_ingested"] == 5
    assert {s["file"] for s in out.summary["files_skipped"]} == {"ground_truth.json", "SHA256SUMS.txt"}


def test_upi_counts_reject_and_dedupe(out):
    f = per_file(out, "upi_logs.csv")
    assert (f["rows_in"], f["records"], f["rejected"], f["duplicates"]) == (264, 259, 2, 3)
    assert all("empty timestamp" in r.reason for r in out.rejected if r.source_file == "upi_logs.csv")


def test_all_laundering_txns_present_and_corroborated(out):
    gt = json.load(open(SYN / "ground_truth.json"))
    tx = {t.txn_id: t for t in out.transactions}
    ids = [i for f in gt["flows"] for i in f["txn_ids"]]
    assert all(i in tx for i in ids) and len(ids) == 21
    assert all(tx[i].corroborated_by for i in ids)


def test_timestamps_are_utc_and_ist_shift_correct(out):
    anydesk = next(a for a in out.artifacts if a.app == "AnyDesk")
    assert anydesk.timestamp.isoformat() == "2026-03-14T05:01:07+00:00"      # 10:31:07 IST


def test_cdr_hidden_caller_kept_and_long_video_call(out):
    assert any(c.caller is None and c.direction == "IN" for c in out.calls)
    assert max(c.duration_sec for c in out.calls if c.call_type == "VIDEO") == 12420
    assert all(c.callee.startswith("+91") for c in out.calls)


def test_ipdr_chunks_merged(out):
    wa = [s for s in out.ip_sessions if s.app_hint and "WhatsApp" in s.app_hint]
    assert len(wa) == 2 and all(s.chunks == 7 for s in wa)
    assert out.summary["totals"]["ipdr_chunks_merged"] == 14


def test_entity_resolution_signal_survives_ingestion(out):
    gt = json.load(open(SYN / "ground_truth.json"))
    shared = gt["shared_resources"]
    devs = {t.sender_account for t in out.transactions if t.device_id == shared["device_id"]}
    assert len(devs) == 2                                                   # M3 and M5 accounts
