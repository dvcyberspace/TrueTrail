"""normalizers.py - small, pure, testable functions. All times -> UTC."""
import hashlib
import ipaddress
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from dateutil import parser as dtparser

from backend.ingestion.config import IST

BLANKS = {"", "null", "none", "na", "n/a", "nan", "-", "--", "nil"}
_UTC_SUFFIX = re.compile(r"\s*\(UTC\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?\)\s*$", re.I)
_EPOCH = re.compile(r"^\d{9,13}(\.\d+)?$")


def is_blank(v: Any) -> bool:
    return v is None or str(v).strip().lower() in BLANKS


def clean(v: Any) -> Optional[str]:
    return None if is_blank(v) else str(v).strip()


def parse_dt(value: Any, assume_tz=IST, formats=()) -> datetime:
    """Epoch (s/ms), ISO-8601, 'DD/MM/YYYY ...', 'DD-MM-YYYY ...(UTC+5:30)'  ->  aware UTC datetime.
    Raises ValueError on anything unparseable (the caller logs it as a rejected row)."""
    if is_blank(value):
        raise ValueError("empty timestamp")
    tz = assume_tz
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) or _EPOCH.match(str(value).strip()):
        x = float(value)
        if x > 1e11:                       # milliseconds
            x /= 1000.0
        dt = datetime.fromtimestamp(x, tz=timezone.utc)
    else:
        s = str(value).strip()
        m = _UTC_SUFFIX.search(s)
        if m:                              # explicit offset in the text wins over assume_tz
            off = timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
            tz = timezone(off if m.group(1) == "+" else -off)
            s = s[: m.start()]
        dt = None
        for f in formats:
            try:
                dt = datetime.strptime(s, f)
                break
            except ValueError:
                continue
        if dt is None and re.match(r"^\d{4}-\d{2}-\d{2}", s):   # ISO - never use dayfirst on these
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                pass
        if dt is None:
            try:
                dt = dtparser.parse(s, dayfirst=True)
            except (ValueError, OverflowError) as e:
                raise ValueError(f"unparseable timestamp {value!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    dt = dt.astimezone(timezone.utc)
    if not 2000 <= dt.year <= 2100:
        raise ValueError(f"timestamp out of range: {value!r}")
    return dt


def norm_phone(raw: Any) -> Optional[str]:
    """'98..', '+9198..', '9198..', '098..' -> '+9198..' ; None if not a valid number."""
    if is_blank(raw):
        return None
    s = str(raw).strip()
    d = re.sub(r"\D", "", s)
    if not d:
        return None
    if s.startswith("+") and not d.startswith("91"):
        return "+" + d if 8 <= len(d) <= 15 else None
    if len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    return "+91" + d if re.fullmatch(r"[6-9]\d{9}", d) else None


def norm_imei(raw: Any) -> Optional[str]:
    d = re.sub(r"\D", "", str(raw)) if not is_blank(raw) else ""
    return d if len(d) == 15 else None


def norm_ip(raw: Any) -> Optional[str]:
    if is_blank(raw):
        return None
    try:
        return str(ipaddress.ip_address(str(raw).strip()))
    except ValueError:
        return None


def norm_account(raw: Any) -> Optional[str]:
    if is_blank(raw):
        return None
    d = re.sub(r"\D", "", str(raw))
    return d if 9 <= len(d) <= 18 else None


def norm_vpa(raw: Any) -> Optional[str]:
    if is_blank(raw):
        return None
    s = str(raw).strip().lower()
    return s if re.fullmatch(r"[\w.\-]{2,}@[a-z][a-z0-9]+", s) else None


def norm_ifsc(raw: Any) -> Optional[str]:
    if is_blank(raw):
        return None
    s = str(raw).strip().upper()
    return s if re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", s) else None


def parse_amount(raw: Any, allow_blank: bool = False) -> Optional[float]:
    """'1,00,000.50', 'Rs. 500', 1000 -> float. Raises ValueError if not a number."""
    if is_blank(raw):
        if allow_blank:
            return None
        raise ValueError("empty amount")
    if isinstance(raw, (int, float)):
        return float(raw)
    s = re.sub(r"(?i)(rs\.?|inr|₹|,|\s)", "", str(raw))
    try:
        return float(s)
    except ValueError as e:
        raise ValueError(f"bad amount {raw!r}") from e


def to_int(raw: Any) -> Optional[int]:
    if is_blank(raw):
        return None
    try:
        return int(float(str(raw).replace(",", "")))
    except ValueError:
        return None


def to_float(raw: Any) -> Optional[float]:
    if is_blank(raw):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def record_hash(*parts: Any) -> str:
    """Stable ID for records without a native key (used for dedupe)."""
    return hashlib.sha1("|".join("" if p is None else str(p) for p in parts).encode()).hexdigest()[:20]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
