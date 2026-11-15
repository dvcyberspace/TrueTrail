"""Telecom IPDR (CSV) -> IPSession, plus merge of contiguous split records."""
from collections import defaultdict
from datetime import timedelta

from backend.ingestion import config as C
from backend.ingestion.normalizers import clean, norm_imei, norm_ip, norm_phone, parse_dt, record_hash, to_int
from backend.ingestion.parsers.base import ParseResult, fname, iter_mapped_csv
from backend.schemas import IPSession


def parse_ipdr(path: str) -> ParseResult:
    spec, name = C.IPDR, fname(path)
    res = ParseResult("ipdr", name)

    def build(m, row_no):
        pub = norm_ip(m.get("public_ip"))
        if not pub:
            raise ValueError(f"invalid public IP {m.get('public_ip')!r}")
        start = parse_dt(m.get("start"), spec["assume_tz"], spec["date_formats"])
        end = parse_dt(m.get("end"), spec["assume_tz"], spec["date_formats"]) if clean(m.get("end")) else None
        if end and end < start:
            raise ValueError("end_time before start_time")
        msisdn = norm_phone(m.get("msisdn"))
        if not msisdn:
            raise ValueError(f"invalid MSISDN {m.get('msisdn')!r}")
        dst, dport = norm_ip(m.get("dst_ip")), to_int(m.get("dst_port"))
        return IPSession(
            record_id=record_hash(msisdn, pub, dst, dport, start.isoformat(), end.isoformat() if end else None,
                                  to_int(m.get("src_port"))),
            start_time=start, end_time=end, msisdn=msisdn, imei=norm_imei(m.get("imei")), imsi=clean(m.get("imsi")),
            private_ip=norm_ip(m.get("private_ip")), src_ip=pub, src_port=to_int(m.get("src_port")),
            dst_ip=dst, dst_port=dport, protocol=(clean(m.get("protocol")) or "").upper() or None,
            bytes_up=to_int(m.get("up")), bytes_down=to_int(m.get("down")), apn=clean(m.get("apn")),
            cell_id=clean(m.get("cell_id")), app_hint=C.APP_SIGNATURES.get((dst, dport)),
            source_file=name, source_row=row_no)

    try:
        res.consume(iter_mapped_csv(path, spec), build, key_fn=lambda r: r.record_id)
    except Exception as e:
        res.reject(0, f"file rejected: {e}")
    return res


def merge_sessions(sessions: list, gap_sec: int = C.IPDR_MERGE_GAP_SEC) -> list:
    """Telcos split long sessions into 30/60-min records. Merge contiguous chunks of the same flow
    (same msisdn, public ip, dst ip/port, protocol) so a 3h27m video call is ONE session."""
    groups = defaultdict(list)
    for s in sessions:
        groups[(s.msisdn, s.src_ip, s.dst_ip, s.dst_port, s.protocol)].append(s)
    out = []
    for g in groups.values():
        g.sort(key=lambda s: s.start_time)
        cur = g[0].model_copy()
        for nxt in g[1:]:
            cur_end = cur.end_time or cur.start_time
            if nxt.start_time - cur_end <= timedelta(seconds=gap_sec):
                cur.end_time = max(cur_end, nxt.end_time or nxt.start_time)
                cur.bytes_up = (cur.bytes_up or 0) + (nxt.bytes_up or 0)
                cur.bytes_down = (cur.bytes_down or 0) + (nxt.bytes_down or 0)
                cur.chunks += nxt.chunks
            else:
                out.append(cur)
                cur = nxt.model_copy()
        out.append(cur)
    out.sort(key=lambda s: s.start_time)
    return out
