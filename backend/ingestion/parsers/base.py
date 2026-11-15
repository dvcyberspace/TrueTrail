"""base.py - shared machinery: column mapping, row loop, rejected-rows log, dedupe."""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional

from pydantic import ValidationError

from backend.schemas import RejectedRow


class ColumnMappingError(Exception):
    """Whole file/sheet can't be mapped (required columns missing)."""


def _key(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def resolve_columns(header: list, spec: dict) -> dict:
    """header cells -> {canonical: column_index} using the alias lists in config."""
    idx = {_key(h): i for i, h in enumerate(header) if h is not None}
    out = {}
    for canon, aliases in spec["columns"].items():
        for a in aliases:
            if _key(a) in idx:
                out[canon] = idx[_key(a)]
                break
    return out


def missing_required(header: list, spec: dict) -> list:
    got = resolve_columns(header, spec)
    return [c for c in spec["required"] if c not in got]


def _reason(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return "ValidationError: " + "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
    return f"{type(e).__name__}: {e}"


@dataclass
class ParseResult:
    source_type: str
    source_file: str
    records: list = field(default_factory=list)
    rows_in: int = 0
    rejected: list = field(default_factory=list)
    duplicates: int = 0
    _seen: set = field(default_factory=set, repr=False)

    def reject(self, row_no: int, reason: str, raw: Any = None, source_file: Optional[str] = None):
        self.rejected.append(RejectedRow(source_file=source_file or self.source_file,
                                         source_row=row_no, reason=reason, raw=raw))

    def consume(self, rows: Iterable, build: Callable, key_fn: Callable,
                source_file: Optional[str] = None):
        """rows: iterable of (row_no, raw_dict). build(raw,row_no)->model (raise = reject).
        Bad rows are LOGGED (never silently dropped); duplicates are counted."""
        for row_no, raw in rows:
            self.rows_in += 1
            try:
                rec = build(raw, row_no)
            except Exception as e:  # noqa: BLE001 - every failure must land in the reject log
                self.reject(row_no, _reason(e), raw, source_file)
                continue
            k = key_fn(rec)
            if k in self._seen:
                self.duplicates += 1
                continue
            self._seen.add(k)
            self.records.append(rec)


def iter_mapped_csv(path: str, spec: dict) -> Iterator[tuple]:
    """Yield (line_number, {canonical: value}) ; header is line 1. Raises ColumnMappingError."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ColumnMappingError("empty file")
        miss = missing_required(header, spec)
        if miss:
            raise ColumnMappingError(f"missing required columns {miss}; header={header}")
        cols = resolve_columns(header, spec)
        for row in reader:
            if not any(c.strip() for c in row):
                continue                                   # blank line, not a record
            yield reader.line_num, {c: (row[i] if i < len(row) else None) for c, i in cols.items()}


def fname(path: str) -> str:
    return Path(path).name
