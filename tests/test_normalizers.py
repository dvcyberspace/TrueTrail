from datetime import datetime, timezone
import pytest
from backend.ingestion.normalizers import *


def test_ist_to_utc():
    assert parse_dt("14/03/2026 11:12:40", formats=["%d/%m/%Y %H:%M:%S"]) == datetime(2026, 3, 14, 5, 42, 40, tzinfo=timezone.utc)

def test_iso_z_stays_utc():
    from backend.ingestion.config import UTC
    assert parse_dt("2026-03-04T05:42:40Z", UTC) == datetime(2026, 3, 4, 5, 42, 40, tzinfo=timezone.utc)

def test_cellebrite_suffix():
    assert parse_dt("14-03-2026 10:29:30(UTC+5:30)", formats=["%d-%m-%Y %H:%M:%S"]).hour == 4

def test_epoch_seconds_and_ms():
    assert parse_dt(1773364200) == parse_dt(1773364200000)

@pytest.mark.parametrize("bad", ["NULL", "", None, "garbage"])
def test_bad_timestamp_raises(bad):
    with pytest.raises(ValueError):
        parse_dt(bad)

@pytest.mark.parametrize("raw", ["9876543210", "+919876543210", "919876543210", "09876543210", "+91 98765 43210"])
def test_phone_variants(raw):
    assert norm_phone(raw) == "+919876543210"

def test_phone_invalid():
    assert norm_phone("UNKNOWN") is None and norm_phone("12345") is None

def test_amount():
    assert parse_amount("1,00,000.50") == 100000.5 and parse_amount("Rs. 500") == 500.0

def test_vpa_account_ip():
    assert norm_vpa(" Rajesh@OKHDFCbank ") == "rajesh@okhdfcbank" and norm_vpa("nope") is None
    assert norm_account("5010-0123-4567-89") == "50100123456789"
    assert norm_ip("49.36.118.77") == "49.36.118.77" and norm_ip("999.1.1.1") is None
