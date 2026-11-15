"""Telecom CDR (CSV) -> CallRecord"""
from datetime import timedelta

from backend.ingestion import config as C
from backend.ingestion.normalizers import clean, norm_imei, norm_phone, parse_dt, record_hash, to_float, to_int
from backend.ingestion.parsers.base import ParseResult, fname, iter_mapped_csv
from backend.schemas import CallRecord


def parse_cdr(path: str) -> ParseResult:
    spec, name = C.CDR, fname(path)
    res = ParseResult("cdr", name)

    def build(m, row_no):
        raw_type = (clean(m.get("call_type")) or "").upper()
        if raw_type not in C.CDR_DIRECTION:
            raise ValueError(f"unknown CALL_TYPE {raw_type!r}")
        direction = C.CDR_DIRECTION[raw_type]
        service = C.CDR_SERVICE.get((clean(m.get("service")) or "").upper())
        if service is None:
            raise ValueError(f"unknown SERVICE {m.get('service')!r}")
        calling, called = norm_phone(m.get("calling")), norm_phone(m.get("called"))
        if not called:
            raise ValueError("missing/invalid called number")
        if direction == "OUT" and not calling:
            raise ValueError("outgoing record without a valid calling number")
        start = parse_dt(m.get("start"), spec["assume_tz"])
        dur = to_int(m.get("duration"))
        if dur is None or dur < 0:
            raise ValueError(f"bad duration {m.get('duration')!r}")
        lat, lon = to_float(m.get("lat")), to_float(m.get("lon"))
        if lat is not None and not -90 <= lat <= 90 or lon is not None and not -180 <= lon <= 180:
            lat = lon = None
        imei = norm_imei(m.get("imei"))
        return CallRecord(
            record_id=record_hash(calling, called, int(start.timestamp()), dur, raw_type, imei),
            start_time=start, end_time=start + timedelta(seconds=dur) if dur else None, duration_sec=dur,
            caller=calling, callee=called, target_number=calling if direction == "OUT" else called,
            direction=direction, call_type=service, raw_type=raw_type, imei=imei,
            imsi=clean(m.get("imsi")), cell_tower_id=clean(m.get("first_cell")),
            last_cell_id=clean(m.get("last_cell")), lac=clean(m.get("lac")),
            latitude=lat, longitude=lon, tower_address=clean(m.get("address")),
            source_file=name, source_row=row_no)

    try:
        res.consume(iter_mapped_csv(path, spec), build, key_fn=lambda r: r.record_id)
    except Exception as e:
        res.reject(0, f"file rejected: {e}")
    return res
