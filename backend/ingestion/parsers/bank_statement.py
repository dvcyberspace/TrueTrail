"""Bank statement (XLSX, one sheet per account) -> Transaction
Handles: metadata block above the table, header row at any position, separate Dr/Cr columns,
narration parsing (UPI-NAME-VPA-IFSC-RRN-remark), footer rows.  PDF statements = stretch goal
(pdfplumber -> same rows -> same build())."""
import re

import openpyxl

from backend.ingestion import config as C
from backend.ingestion.normalizers import (clean, norm_account, norm_ifsc, norm_vpa, parse_amount, parse_dt,
                                           record_hash)
from backend.ingestion.parsers.base import ColumnMappingError, ParseResult, fname, resolve_columns, missing_required
from backend.schemas import Transaction


def _norm_label(s):
    return re.sub(r"[^a-z0-9/ ]", "", str(s).lower()).strip()


def parse_bank_statement(path: str, profile: str = "default") -> ParseResult:
    prof, name = C.BANK_PROFILES[profile], fname(path)
    res = ParseResult("bank_statement", name)
    upi_re = re.compile(prof["upi_narration"])
    rules = [(re.compile(p), ch) for p, ch in prof["channel_rules"]]

    wb = openpyxl.load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        sheet_file = f"{name}#{ws.title}"
        rows = [(i, list(r)) for i, r in enumerate(ws.iter_rows(values_only=True), start=1)]

        # 1) locate header row + read metadata block
        header_i, meta = None, {}
        for i, r in rows:
            if header_i is None and not missing_required([c for c in r], prof):
                header_i = i
                break
            first = clean(r[0]) if r else None
            if first and first.upper().startswith(prof["title_prefix"]) and "-" in first:
                meta["bank"] = first.split("-", 1)[1].strip().title()
            elif first and first.endswith(":") and len(r) > 1:
                for canon, aliases in prof["meta_labels"].items():
                    if _norm_label(first.rstrip(":")) in [_norm_label(a) for a in aliases]:
                        meta[canon] = r[1]
        if header_i is None:
            res.reject(0, f"sheet rejected: no header row with {prof['required']}", source_file=sheet_file)
            continue
        acct = norm_account(meta.get("account_no"))
        if not acct:
            res.reject(0, "sheet rejected: account number not found in header block", source_file=sheet_file)
            continue
        own_ifsc, own_name = norm_ifsc(meta.get("ifsc")), clean(meta.get("account_name"))
        cols = resolve_columns(rows[header_i - 1][1], prof)

        # 2) data rows
        def data_rows():
            for i, r in rows[header_i:]:
                if not any(c is not None and str(c).strip() for c in r):
                    continue                                       # blank
                if str(r[0]).strip().startswith("***"):
                    continue                                       # footer
                yield i, {c: (r[j] if j < len(r) else None) for c, j in cols.items()}

        def build(m, row_no, acct=acct, own_ifsc=own_ifsc, own_name=own_name, sheet_file=sheet_file):
            ts = parse_dt(m.get("txn_date"), prof["assume_tz"], prof["date_formats"])
            dr = parse_amount(m.get("debit"), allow_blank=True) or 0.0
            cr = parse_amount(m.get("credit"), allow_blank=True) or 0.0
            if dr > 0 and cr > 0:
                raise ValueError("both debit and credit populated")
            if dr <= 0 and cr <= 0:
                raise ValueError("no debit/credit amount")
            amount, direction = (dr, "DEBIT") if dr > 0 else (cr, "CREDIT")
            narr = clean(m.get("narration")) or ""
            channel = next((ch for rx, ch in rules if rx.match(narr)), "OTHER")
            mu = upi_re.match(narr) if channel == "UPI" else None
            rrn = mu.group("rrn") if mu else None
            cp = dict(vpa=norm_vpa(mu.group("vpa")), ifsc=norm_ifsc(mu.group("ifsc")),
                      name=clean(mu.group("name")).title()) if mu else {}
            own = dict(account=acct, ifsc=own_ifsc, name=own_name)
            if direction == "DEBIT":
                parties = dict(sender_account=acct, sender_ifsc=own_ifsc, sender_name=own_name,
                               receiver_vpa=cp.get("vpa"), receiver_ifsc=cp.get("ifsc"), receiver_name=cp.get("name"))
            else:
                parties = dict(receiver_account=acct, receiver_ifsc=own_ifsc, receiver_name=own_name,
                               sender_vpa=cp.get("vpa"), sender_ifsc=cp.get("ifsc"), sender_name=cp.get("name"))
            ref = clean(m.get("ref_no"))
            txn_id = (f"BS-{rrn}-{direction[0]}" if rrn
                      else "BS-" + record_hash(acct, ts.isoformat(), narr, ref, amount, direction))
            bal = parse_amount(m.get("balance"), allow_blank=True)
            return Transaction(
                txn_id=txn_id, rrn=rrn, timestamp=ts, channel=channel, amount=amount, direction=direction,
                remarks=(clean(mu.group("remark")) if mu else None), narration=narr or None,
                balance_after=bal, source_type="BANK_STATEMENT", source_file=sheet_file, source_row=row_no,
                **parties)

        res.consume(data_rows(), build, key_fn=lambda t: t.txn_id, source_file=sheet_file)
    return res
