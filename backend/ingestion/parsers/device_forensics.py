"""Cellebrite-style JSON extraction -> DeviceArtifact
(Real UFED/Autopsy exports are XML/SQLite/Excel; add a reader that yields the same dict shapes.)"""
import json

from backend.ingestion import config as C
from backend.ingestion.normalizers import clean, norm_imei, norm_phone, parse_dt, record_hash
from backend.ingestion.parsers.base import ColumnMappingError, ParseResult, fname
from backend.schemas import DeviceArtifact

DIR = {"incoming": "IN", "outgoing": "OUT", "in": "IN", "out": "OUT"}


def _ts(v):
    return parse_dt(v, C.DEVICE["assume_tz"], C.DEVICE["date_formats"]) if clean(v) else None


def _party(v):
    return norm_phone(v) or clean(v)            # "Mom" stays "Mom"


def parse_device_dump(path: str) -> ParseResult:
    name = fname(path)
    res = ParseResult("device", name)
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    imei = norm_imei(doc.get("report_header", {}).get("device", {}).get("imei"))
    if not imei:
        res.reject(0, "file rejected: device IMEI missing in report_header")
        return res
    key = lambda a: a.artifact_id  # noqa: E731

    def mk(kind, aid, row_no, src, **kw):
        return DeviceArtifact(artifact_id=f"{imei}:{kind}:{aid}", device_id=imei, artifact_type=kind,
                              source_file=src, source_row=row_no, **kw)

    # installed apps
    src = f"{name}#installed_applications"
    res.consume(enumerate(doc.get("installed_applications", []), 1),
                lambda a, n: mk("INSTALLED_APP", clean(a.get("package")) or record_hash(a.get("name")), n, src,
                                app=clean(a.get("name")), timestamp=_ts(a.get("install_time")),
                                content=f"{a.get('package')} v{a.get('version')}",
                                extra={"package": a.get("package"), "version": a.get("version"),
                                       "last_used": (_ts(a.get("last_used")).isoformat() if _ts(a.get("last_used")) else None)}),
                key, src)

    # chats
    for chat in doc.get("chats", []):
        src = f"{name}#chats/{chat.get('chat_id')}"

        def build_msg(m, n, chat=chat, src=src):
            d = DIR.get(str(m.get("direction", "")).lower())
            return mk("CHAT", clean(m.get("msg_id")) or record_hash(m.get("timestamp"), m.get("body")), n, src,
                      app=chat.get("source_app"), timestamp=_ts(m.get("timestamp")), direction=d,
                      counterparty=_party(m.get("from") if d == "IN" else m.get("to")),
                      content=clean(m.get("body")), deleted=bool(m.get("deleted")),
                      extra={"chat_id": chat.get("chat_id"), "status": m.get("status")})

        res.consume(enumerate(chat.get("messages", []), 1), build_msg, key, src)

    # sms
    src = f"{name}#sms_messages"
    res.consume(enumerate(doc.get("sms_messages", []), 1),
                lambda s, n: mk("SMS", clean(s.get("sms_id")) or record_hash(s.get("timestamp"), s.get("body")), n, src,
                                app="SMS", timestamp=_ts(s.get("timestamp")), direction="IN",
                                counterparty=clean(s.get("sender")), content=clean(s.get("body"))),
                key, src)

    # call log
    src = f"{name}#call_log"
    res.consume(enumerate(doc.get("call_log", []), 1),
                lambda c, n: mk("CALL_LOG", clean(c.get("call_id")) or record_hash(c.get("timestamp"), c.get("number")), n, src,
                                app=clean(c.get("type")), timestamp=_ts(c.get("timestamp")),
                                direction=DIR.get(str(c.get("direction", "")).lower()),
                                counterparty=_party(c.get("number")),
                                content=f"{c.get('type')} {c.get('duration_sec')}s",
                                extra={"duration_sec": c.get("duration_sec")}),
                key, src)

    # contacts
    src = f"{name}#contacts"
    res.consume(enumerate(doc.get("contacts", []), 1),
                lambda c, n: mk("CONTACT", record_hash(c.get("name"), c.get("number")), n, src,
                                counterparty=_party(c.get("number")), content=clean(c.get("name"))),
                key, src)
    return res
