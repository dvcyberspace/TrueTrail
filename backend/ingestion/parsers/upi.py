"""UPI switch / PSP log (CSV) -> Transaction"""
from backend.ingestion import config as C
from backend.ingestion.normalizers import (clean, norm_account, norm_ifsc, norm_ip, norm_phone, norm_vpa,
                                           parse_amount, parse_dt)
from backend.ingestion.parsers.base import ParseResult, fname, iter_mapped_csv
from backend.schemas import Transaction

STATUS = {"SUCCESS": "SUCCESS", "SUCCESSFUL": "SUCCESS", "FAILED": "FAILED", "FAILURE": "FAILED",
          "PENDING": "PENDING", "DEFERRED": "PENDING"}


def parse_upi(path: str) -> ParseResult:
    spec, name = C.UPI, fname(path)
    res = ParseResult("upi", name)

    def build(m, row_no):
        txn_id = clean(m.get("txn_id"))
        if not txn_id:
            raise ValueError("missing txn_id")
        ts = parse_dt(m.get("timestamp"), spec["assume_tz"], spec["date_formats"])
        amount = parse_amount(m.get("amount"))
        s_vpa, s_acct = norm_vpa(m.get("payer_vpa")), norm_account(m.get("payer_account"))
        r_vpa, r_acct = norm_vpa(m.get("payee_vpa")), norm_account(m.get("payee_account"))
        if not (s_vpa or s_acct):
            raise ValueError("no usable payer identifier (VPA/account)")
        if not (r_vpa or r_acct):
            raise ValueError("no usable payee identifier (VPA/account)")
        status = STATUS.get((clean(m.get("status")) or "SUCCESS").upper(), clean(m.get("status")).upper())
        return Transaction(
            txn_id=txn_id, rrn=clean(m.get("rrn")), timestamp=ts, channel="UPI", amount=amount,
            currency=(clean(m.get("currency")) or "INR").upper(),
            sender_account=s_acct, sender_vpa=s_vpa, sender_ifsc=norm_ifsc(m.get("payer_ifsc")),
            sender_name=clean(m.get("payer_name")), sender_mobile=norm_phone(m.get("payer_mobile")),
            receiver_account=r_acct, receiver_vpa=r_vpa, receiver_ifsc=norm_ifsc(m.get("payee_ifsc")),
            receiver_name=clean(m.get("payee_name")),
            device_id=clean(m.get("device_id")), ip_address=norm_ip(m.get("ip")),
            app_name=clean(m.get("app_name")), status=status,
            response_code=clean(m.get("response_code")), remarks=clean(m.get("remarks")),
            source_type="UPI_LOG", source_file=name, source_row=row_no)

    try:
        res.consume(iter_mapped_csv(path, spec), build, key_fn=lambda t: t.txn_id)
    except Exception as e:  # file-level problem
        res.reject(0, f"file rejected: {e}")
    return res
