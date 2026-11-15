from datetime import timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

# files that are never evidence
IGNORE_FILES = {"ground_truth.json", "SHA256SUMS.txt"}

# --------------------------------------------------------------------------- UPI switch / PSP log
UPI = {
    "assume_tz": UTC,
    "date_formats": [],                                   # ISO-8601 handled natively
    "required": ["txn_id", "timestamp", "amount"],
    "columns": {
        "txn_id": ["Txn_ID", "Transaction ID", "TxnId"],
        "rrn": ["RRN", "Ref No", "UPI Ref No"],
        "timestamp": ["Txn_Timestamp_UTC", "Txn Timestamp", "Transaction Date Time", "Timestamp"],
        "txn_type": ["Txn_Type", "Type"],
        "payer_vpa": ["Payer_VPA", "Payer VPA", "Remitter VPA"],
        "payer_name": ["Payer_Name", "Remitter Name"],
        "payer_account": ["Payer_Account", "Payer Acct", "Remitter Account"],
        "payer_ifsc": ["Payer_IFSC", "Remitter IFSC"],
        "payer_mobile": ["Payer_Mobile", "Payer Mobile No"],
        "payee_vpa": ["Payee_VPA", "Payee VPA", "Beneficiary VPA"],
        "payee_name": ["Payee_Name", "Beneficiary Name"],
        "payee_account": ["Payee_Account", "Beneficiary Account"],
        "payee_ifsc": ["Payee_IFSC", "Beneficiary IFSC"],
        "amount": ["Amount", "Txn Amount", "Amount (INR)"],
        "currency": ["Currency"],
        "status": ["Status", "Txn Status"],
        "response_code": ["Response_Code", "Resp Code"],
        "device_id": ["Device_ID", "Device Id", "Payer Device"],
        "ip": ["Device_IP", "IP Address", "Payer IP"],
        "app_name": ["App_Name", "PSP App"],
        "remarks": ["Remarks", "Note"],
    },
}

# --------------------------------------------------------------------------- Telecom CDR
CDR = {
    "assume_tz": UTC,                                     # epoch seconds are UTC by definition
    "required": ["called", "call_type", "start"],
    "columns": {
        "calling": ["CALLING_NO", "A_PARTY", "Calling Number", "A Party"],
        "called": ["CALLED_NO", "B_PARTY", "Called Number", "B Party"],
        "call_type": ["CALL_TYPE", "Call Type"],
        "service": ["SERVICE", "Service Type"],
        "start": ["START_EPOCH", "Call Start", "Start Time"],
        "duration": ["DURATION_SEC", "Duration"],
        "imei": ["IMEI"],
        "imsi": ["IMSI"],
        "first_cell": ["FIRST_CELL_ID", "Cell ID A", "Cell ID"],
        "last_cell": ["LAST_CELL_ID", "Last Cell ID"],
        "lac": ["LAC"],
        "lat": ["TOWER_LAT", "Latitude"],
        "lon": ["TOWER_LON", "Longitude"],
        "address": ["TOWER_ADDR", "Site Address", "Address"],
    },
}
CDR_DIRECTION = {"MOC": "OUT", "SMS-MO": "OUT", "MTC": "IN", "SMS-MT": "IN"}
CDR_SERVICE = {"VOICE": "VOICE", "VIDEO": "VIDEO", "SMS": "SMS", "DATA": "DATA"}
CDR_TARGET_IS_CALLER = {"OUT": True, "IN": False}

# --------------------------------------------------------------------------- Telecom IPDR
IPDR = {
    "assume_tz": IST,
    "date_formats": ["%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"],
    "required": ["msisdn", "public_ip", "start"],
    "columns": {
        "msisdn": ["MSISDN", "Subscriber Number"],
        "imei": ["IMEI"],
        "imsi": ["IMSI"],
        "private_ip": ["PRIVATE_IP", "Private IP"],
        "public_ip": ["PUBLIC_IP", "Public IP", "Source Public IP"],
        "src_port": ["SRC_PORT", "Source Port"],
        "dst_ip": ["DST_IP", "Destination IP"],
        "dst_port": ["DST_PORT", "Destination Port"],
        "protocol": ["PROTOCOL"],
        "start": ["START_TIME", "Session Start"],
        "end": ["END_TIME", "Session End"],
        "up": ["UPLINK_BYTES", "Uplink Volume"],
        "down": ["DOWNLINK_BYTES", "Downlink Volume"],
        "apn": ["APN"],
        "cell_id": ["CELL_ID", "Cell Id"],
    },
}
# (dst_ip, dst_port) -> label.  Real life: build from IP-range lookups / lawful-intercept notes.
APP_SIGNATURES = {
    ("203.0.113.45", 3478): "WhatsApp (call relay)",
    ("198.51.100.77", 7070): "AnyDesk (remote access)",
    ("192.0.2.10", 443): "Mobile banking app",
}
IPDR_MERGE_GAP_SEC = 5          # contiguous chunks (gap <= this) of the same flow become one session

# --------------------------------------------------------------------------- Bank statements (xlsx)
BANK_PROFILES = {
    "default": {
        "assume_tz": IST,
        "date_formats": ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"],
        "required": ["txn_date", "narration"],
        "columns": {
            "txn_date": ["Txn Date", "Transaction Date", "Date"],
            "value_date": ["Value Date"],
            "narration": ["Narration", "Description", "Particulars", "Transaction Remarks"],
            "ref_no": ["Chq/Ref No", "Ref No", "Cheque No", "Reference"],
            "debit": ["Withdrawal Amt (Dr)", "Withdrawal", "Debit", "Dr Amount"],
            "credit": ["Deposit Amt (Cr)", "Deposit", "Credit", "Cr Amount"],
            "balance": ["Closing Balance", "Balance"],
        },
        # metadata block above the table:  canonical -> label aliases
        "meta_labels": {
            "account_no": ["Account No", "Account Number", "A/c No"],
            "account_name": ["Account Name", "Customer Name"],
            "ifsc": ["IFSC", "IFSC Code"],
        },
        "title_prefix": "STATEMENT OF ACCOUNT",
        # ordered (regex, channel) - first match wins; UPI is parsed with UPI_NARRATION below
        "channel_rules": [
            (r"^UPI", "UPI"), (r"^NEFT", "NEFT"), (r"^IMPS", "IMPS"),
            (r"^RTGS", "RTGS"), (r"^ATM", "ATM"),
        ],
        "upi_narration": r"^UPI-(?P<name>.+?)-(?P<vpa>[\w.\-]+@[A-Za-z0-9]+)-(?P<ifsc>[A-Z]{4}0[A-Z0-9]{6})-(?P<rrn>\d{12})-?(?P<remark>.*)$",
    },
    # add "sbi": {...}, "icici": {...} here when a new statement layout shows up
}

# --------------------------------------------------------------------------- Device forensics (Cellebrite-style JSON)
DEVICE = {
    "assume_tz": IST,                                     # suffix "(UTC+5:30)" is parsed and wins
    "date_formats": ["%d-%m-%Y %H:%M:%S"],
}
