"""
schemas.py  -  Canonical data contract (v1.1)   [shared by all 4 members]

Changes vs v1.0 (needed to match the real-format synthetic data):
  Transaction  : + rrn, direction, names, mobile, app_name, response_code, remarks, narration,
                 balance_after, source_type, corroborated_by      (bank statements carry narration/balance;
                 UPI logs carry names/app/response code; RRN is the key that links the two)
  CallRecord   : caller now Optional (hidden caller ID), + direction (IN/OUT from MOC/MTC),
                 target_number, raw_type, last_cell_id, lac, tower_address
  IPSession    : + private_ip, dst_port, protocol, imei, imsi, apn, cell_id, chunks
                 (src_ip == the PUBLIC IP, the one that matters for correlation)
  DeviceArtifact: + SMS type, direction, deleted flag, extra{} (package, version, last_used...)
  EvidenceItem : + rows_in / rejected_count / duplicate_count / schema_version
  NEW          : RejectedRow
Every datetime is validated to be timezone-aware and is converted to UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.1"


def _to_utc(v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError("naive datetime not allowed - normalise to UTC first")
    return v.astimezone(timezone.utc)


UTCDatetime = Annotated[datetime, AfterValidator(_to_utc)]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Transaction(_Base):
    txn_id: str
    rrn: Optional[str] = None                       # 12-digit UPI reference; links UPI log <-> statement
    timestamp: UTCDatetime
    channel: Literal["UPI", "IMPS", "NEFT", "RTGS", "ATM", "OTHER"]
    amount: float = Field(gt=0)
    currency: str = "INR"
    direction: Optional[Literal["DEBIT", "CREDIT"]] = None   # only known for bank statements
    sender_account: Optional[str] = None
    sender_vpa: Optional[str] = None
    sender_ifsc: Optional[str] = None
    sender_name: Optional[str] = None
    sender_mobile: Optional[str] = None
    receiver_account: Optional[str] = None
    receiver_vpa: Optional[str] = None
    receiver_ifsc: Optional[str] = None
    receiver_name: Optional[str] = None
    device_id: Optional[str] = None                 # payer app/device fingerprint (UPI log)
    ip_address: Optional[str] = None                # payer IP (UPI log)
    app_name: Optional[str] = None
    status: str = "SUCCESS"
    response_code: Optional[str] = None
    remarks: Optional[str] = None
    narration: Optional[str] = None                 # raw bank narration
    balance_after: Optional[float] = None
    source_type: Literal["UPI_LOG", "BANK_STATEMENT"]
    corroborated_by: list[str] = Field(default_factory=list)  # other files confirming this txn
    source_file: str                                # provenance
    source_row: int                                 # provenance


class CallRecord(_Base):
    record_id: str
    start_time: UTCDatetime
    end_time: Optional[UTCDatetime] = None
    duration_sec: int = Field(ge=0)
    caller: Optional[str] = None                    # E.164, None = hidden caller ID
    callee: str                                     # E.164
    target_number: Optional[str] = None             # the subscriber whose CDR this row is
    direction: Literal["IN", "OUT"]                 # MOC/SMS-MO -> OUT ; MTC/SMS-MT -> IN
    call_type: Literal["VOICE", "VIDEO", "SMS", "DATA"]
    raw_type: Optional[str] = None                  # MOC / MTC / SMS-MO / SMS-MT
    imei: Optional[str] = None
    imsi: Optional[str] = None
    cell_tower_id: Optional[str] = None             # first cell
    last_cell_id: Optional[str] = None
    lac: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    tower_address: Optional[str] = None
    source_file: str
    source_row: int


class IPSession(_Base):
    record_id: str
    start_time: UTCDatetime
    end_time: Optional[UTCDatetime] = None
    msisdn: Optional[str] = None                    # E.164
    imei: Optional[str] = None
    imsi: Optional[str] = None
    private_ip: Optional[str] = None
    src_ip: str                                     # PUBLIC IP of the subscriber
    src_port: Optional[int] = None
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None
    bytes_up: Optional[int] = None
    bytes_down: Optional[int] = None
    apn: Optional[str] = None
    cell_id: Optional[str] = None
    app_hint: Optional[str] = None                  # inferred from dst ip/port (config.APP_SIGNATURES)
    chunks: int = 1                                 # >1 when split IPDR records were merged
    source_file: str
    source_row: int


class DeviceArtifact(_Base):
    artifact_id: str
    device_id: str                                  # IMEI from the extraction report
    artifact_type: Literal["CHAT", "SMS", "INSTALLED_APP", "CONTACT", "CALL_LOG", "OTHER"]
    app: Optional[str] = None
    timestamp: Optional[UTCDatetime] = None
    direction: Optional[Literal["IN", "OUT"]] = None
    counterparty: Optional[str] = None
    content: Optional[str] = None
    deleted: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)
    source_file: str
    source_row: int


class EvidenceItem(_Base):
    evidence_id: str
    filename: str
    sha256: str
    evidence_type: str                              # upi | cdr | bank_statement | ipdr | device
    ingested_at: UTCDatetime
    record_count: int
    rows_in: int = 0
    rejected_count: int = 0
    duplicate_count: int = 0
    schema_version: str = SCHEMA_VERSION


class RejectedRow(_Base):
    source_file: str
    source_row: int                                 # 0 = whole file / sheet rejected
    reason: str
    raw: Any = None
