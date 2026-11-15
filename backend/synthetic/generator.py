#!/usr/bin/env python3
"""
generator.py - Synthetic evidence generator (Member 1)

WHERE TO PUT IT : forensic-engine/backend/synthetic/generator.py
HOW TO RUN      : from repo root ->  python backend/synthetic/generator.py
OUTPUT          : forensic-engine/data/synthetic/

*** ALL DATA IS FABRICATED. No real person, account, number or device. ***
(IPs used as destinations come from RFC 5737 documentation ranges.)

Scripted "digital arrest" scenario (14-Mar-2026, IST):
  * Victim V gets a voice call + a 3h27m video call from fake officer P1.
  * During the call V makes 3 UPI transfers to mule M1.
  * Each transfer is layered  V -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> CX (crypto exchange),
    every hop 1-6 minutes apart, each mule keeps 5% (forwards 95%).
  * M3 and M5 share one handset (same IMEI), device ID and public IP.
  * Handler H1 phones each mule shortly before it forwards the money (mastermind link).
  * Victim's phone dump has AnyDesk installed mid-call + WhatsApp chat with P1 + bank SMS.
  * ~240 noise UPI txns, ~170 noise calls, ~90 noise IPDR sessions, with a few deliberately
    dirty rows (duplicates, bad timestamps, hidden numbers) to exercise the parsers.

Files written (each mimics a different real-world source):
  upi_logs.csv        UPI switch/PSP log          ISO-8601 UTC timestamps
  bank_statement.xlsx Bank statement, 1 sheet per account, IST 'DD/MM/YYYY HH:MM:SS',
                      metadata header block, different column order, narration needs parsing
  cdr.csv             Telecom CDR                 epoch seconds, mixed phone formats, tower lat/lon
  ipdr.csv            Telecom IPDR                IST 'DD-MM-YYYY HH:MM:SS', MSISDN as 91XXXXXXXXXX
  device_dump.json    Cellebrite-style export     'DD-MM-YYYY HH:MM:SS(UTC+5:30)' timestamps
  ground_truth.json   ANSWER KEY for Members 2/3/4 (do NOT feed to parsers)
  SHA256SUMS.txt      hash manifest (what police attach to evidence)

NOTE: commit the generated files and do NOT regenerate casually - the .xlsx embeds a
timestamp so its SHA-256 changes on every run (the other files are byte-identical).
"""
import csv
import hashlib
import json
import random
import string
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

SEED = 42
rnd = random.Random(SEED)
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc
OUT = Path(__file__).resolve().parents[2] / "data" / "synthetic"
OUT.mkdir(parents=True, exist_ok=True)

NOISE_START = datetime(2026, 3, 13, 6, 0, tzinfo=IST)
NOISE_END = datetime(2026, 3, 15, 22, 0, tzinfo=IST)


# ----------------------------------------------------------------------------- helpers
def at(day, h, m, s=0):
    return datetime(2026, 3, day, h, m, s, tzinfo=IST)


def digits(n):
    return "".join(rnd.choice(string.digits) for _ in range(n))


def hexid(n):
    return "".join(rnd.choice("0123456789abcdef") for _ in range(n))


def rand_time(start=NOISE_START, end=NOISE_END):
    return start + timedelta(seconds=rnd.randint(0, int((end - start).total_seconds())))


def luhn_digit(body):
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def make_imei():
    body = "35" + digits(12)
    return body + luhn_digit(body)  # valid 15-digit IMEI


def make_ip():
    return f"{rnd.choice([49, 106, 117, 152])}.{rnd.randint(1, 254)}.{rnd.randint(1, 254)}.{rnd.randint(1, 254)}"


def ist_str(ts, fmt):
    return ts.astimezone(IST).strftime(fmt)


# ----------------------------------------------------------------------------- towers
CITIES = {
    "Pune": (18.5204, 73.8567), "Jaipur": (26.9124, 75.7873), "Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777), "Kolkata": (22.5726, 88.3639), "Hyderabad": (17.3850, 78.4867),
    "Bengaluru": (12.9716, 77.5946), "Ahmedabad": (23.0225, 72.5714), "Lucknow": (26.8467, 80.9462),
    "Surat": (21.1702, 72.8311),
}
TOWERS = {}
for _city, (_la, _lo) in CITIES.items():
    for _k in range(1, 4):
        cid = str(rnd.randint(10000, 65000))
        while cid in TOWERS:
            cid = str(rnd.randint(10000, 65000))
        TOWERS[cid] = {"lac": str(rnd.randint(1000, 9999)),
                       "lat": round(_la + rnd.uniform(-0.05, 0.05), 6),
                       "lon": round(_lo + rnd.uniform(-0.05, 0.05), 6),
                       "addr": f"BTS-{_k}, {_city}", "city": _city}


def pick_tower(city):
    return rnd.choice([c for c, t in TOWERS.items() if t["city"] == city])


# ----------------------------------------------------------------------------- entities
BANKS = [  # (bank name, IFSC prefix, UPI handle)
    ("HDFC Bank", "HDFC", "okhdfcbank"), ("State Bank of India", "SBIN", "oksbi"),
    ("ICICI Bank", "ICIC", "okicici"), ("Axis Bank", "UTIB", "okaxis"),
    ("Yes Bank", "YESB", "ybl"), ("Kotak Mahindra Bank", "KKBK", "ibl"),
    ("Punjab National Bank", "PUNB", "pnb"), ("Bank of Baroda", "BARB", "barodampay"),
]


def make_entity(name, city, bank_idx=None):
    bank, pfx, handle = BANKS[bank_idx] if bank_idx is not None else rnd.choice(BANKS)
    first = name.split()[0].lower()
    return {
        "name": name, "city": city, "bank": bank,
        "acct": digits(14), "ifsc": f"{pfx}0{digits(6)}",
        "vpa": f"{first}{digits(rnd.randint(2, 4))}@{handle}",
        "phone": rnd.choice("6789") + digits(9),
        "imei": make_imei(), "imsi": "40445" + digits(10),
        "device": hexid(16), "ip": make_ip(), "cell": pick_tower(city),
    }


E = {
    "V": make_entity("Rajesh Kumar Sharma", "Pune", bank_idx=0),
    "P1": make_entity("Fake Officer (P1)", "Jaipur"),
    "H1": make_entity("Handler (H1)", "Kolkata"),
    "M1": make_entity("Amit Tiwari", "Lucknow"),
    "M2": make_entity("Sunita Devi", "Hyderabad"),
    "M3": make_entity("Rohan Mehta", "Delhi"),
    "M4": make_entity("Kavita Singh", "Bengaluru"),
    "M5": make_entity("Imran Sheikh", "Delhi"),
    "M6": make_entity("Pooja Nair", "Ahmedabad"),
    "CX": make_entity("Nexa Digital Assets Pvt Ltd", "Mumbai"),
}
# entity-resolution test: M3 and M5 use the SAME handset / device / public IP
for _f in ("imei", "device", "ip", "cell"):
    E["M5"][_f] = E["M3"][_f]
E["CX"]["vpa"] = "nexadigital.pay@ybl"

FIRST = ["Anil", "Priya", "Suresh", "Neha", "Vikas", "Meena", "Arjun", "Divya", "Manoj", "Rekha",
         "Karan", "Anita", "Sanjay", "Lata", "Nitin", "Seema", "Rahul", "Geeta", "Ajay", "Swati"]
LAST = ["Patil", "Gupta", "Reddy", "Joshi", "Khan", "Das", "Iyer", "Bose", "Kulkarni", "Shah",
        "Pandey", "Rao", "Chopra", "Menon", "Saxena"]
MERCH = ["Bright Mart", "City Metro Recharge", "Fresh Basket Grocers", "QuickBite Foods",
         "Sai Medicals", "Urban Cab Services", "Green Leaf Cafe", "PowerGrid Bill Pay"]
NOISE = []
for _fn, _ln in rnd.sample(list(product(FIRST, LAST)), 40):
    NOISE.append(make_entity(f"{_fn} {_ln}", rnd.choice(list(CITIES))))
for _m in MERCH:
    NOISE.append(make_entity(_m, rnd.choice(list(CITIES))))

CHAIN = ["V", "M1", "M2", "M3", "M4", "M5", "M6", "CX"]
BANK_KEYS = ["V", "M1", "M2", "M3", "M4", "M5", "M6", "CX"]

# ----------------------------------------------------------------------------- transactions
TXNS = []
_used_rrn = set()


def new_rrn():
    while True:
        r = "6" + digits(11)
        if r not in _used_rrn:
            _used_rrn.add(r)
            return r


def add_txn(ts, payer, payee, amount, remark="", status="SUCCESS", tag="noise"):
    t = {"txn_id": f"{payer['ifsc'][:3]}{hexid(29).upper()}", "rrn": new_rrn(),
         "ts": ts.astimezone(UTC), "payer": payer, "payee": payee, "amount": amount,
         "status": status, "remark": remark, "tag": tag}
    TXNS.append(t)
    return t


# --- scripted laundering flows
V_TIMES = [at(14, 11, 12, 40), at(14, 12, 5, 18), at(14, 13, 10, 55)]
V_AMTS = [100000.00, 100000.00, 90000.00]
FLOWS = []
for fi, (t0, a0) in enumerate(zip(V_TIMES, V_AMTS), 1):
    cur, amt, txn_ids, hop_times = t0, a0, [], []
    for i in range(len(CHAIN) - 1):
        if i > 0:
            cur += timedelta(seconds=rnd.randint(60, 360))
            amt = round(amt * 0.95, 2)  # mule keeps 5%
        remark = "RBI verification" if i == 0 else rnd.choice(["Payment", "Transfer", "Goods", "Rent", "Loan"])
        t = add_txn(cur, E[CHAIN[i]], E[CHAIN[i + 1]], amt, remark, tag=f"flow{fi}_hop{i + 1}")
        txn_ids.append(t["txn_id"])
        hop_times.append(cur)
    FLOWS.append({"flow": fi, "txn_ids": txn_ids, "hop_times": hop_times})

# --- noise
pool = NOISE + [E[k] for k in BANK_KEYS]
scenario_banks = {id(E[k]) for k in BANK_KEYS}
while sum(1 for t in TXNS if t["tag"] == "noise") < 240:
    a, b = rnd.sample(pool, 2)
    if id(a) in scenario_banks and id(b) in scenario_banks:
        continue  # keep noise from creating fake mule links
    amount = round(min(max(rnd.lognormvariate(6.2, 1.1), 10), 50000), 2)
    if id(a) in scenario_banks or id(b) in scenario_banks:
        amount = round(min(amount, 1500), 2)
    failed = rnd.random() < 0.04
    add_txn(rand_time(), a, b, amount, rnd.choice(["", "UPI", "Dinner", "Bill", "Thanks", "Rent share"]),
            status="FAILED" if failed else "SUCCESS")
TXNS.sort(key=lambda t: t["ts"])

# ----------------------------------------------------------------------------- 1) upi_logs.csv
UPI_COLS = ["Txn_ID", "RRN", "Txn_Timestamp_UTC", "Txn_Type", "Payer_VPA", "Payer_Name", "Payer_Account",
            "Payer_IFSC", "Payer_Mobile", "Payee_VPA", "Payee_Name", "Payee_Account", "Payee_IFSC",
            "Amount", "Currency", "Status", "Response_Code", "Device_ID", "Device_IP", "App_Name", "Remarks"]


def upi_row(t):
    p, q = t["payer"], t["payee"]
    return [t["txn_id"], t["rrn"], t["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), "PAY", p["vpa"], p["name"],
            p["acct"], p["ifsc"], "91" + p["phone"], q["vpa"], q["name"], q["acct"], q["ifsc"],
            f"{t['amount']:.2f}", "INR", t["status"],
            "00" if t["status"] == "SUCCESS" else rnd.choice(["U16", "U30", "ZM", "U17"]),
            p["device"], p["ip"], rnd.choice(["GPay", "PhonePe", "Paytm", "BHIM", "BankApp"]), t["remark"]]


upi_rows = [upi_row(t) for t in TXNS]
noise_idx = [i for i, t in enumerate(TXNS) if t["tag"] == "noise"]
for i in rnd.sample(noise_idx, 3):                 # duplicate rows (dedupe test)
    upi_rows.append(list(upi_rows[i]))
for i in rnd.sample(noise_idx, 2):                 # corrupted timestamp (reject-log test)
    upi_rows[i][2] = "NULL"
upi_rows[rnd.choice(noise_idx)][9] = ""            # missing payee VPA
with open(OUT / "upi_logs.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(UPI_COLS)
    w.writerows(upi_rows)

# ----------------------------------------------------------------------------- 2) bank_statement.xlsx
OPENING = {"V": 1850000.00, "CX": 5000000.00}
EXTRAS = {k: [] for k in BANK_KEYS}
EXTRAS["V"] += [(at(13, 9, 0), f"NEFT CR-{E['V']['ifsc']}-PUNE TECHSERV LLP-SALARY MAR-{digits(10)}", digits(10), 0, 62500.00),
                (at(13, 18, 20), "ATM WDL-S1ANPN04-PUNE", digits(6), 5000.00, 0)]
for k in ("M1", "M2", "M3", "M4", "M5", "M6"):
    EXTRAS[k] += [(at(13, 11, rnd.randint(0, 59)), "CASH DEP BY SELF-BRANCH", digits(6), 0, 20000.00),
                  (at(15, 9, rnd.randint(0, 59)), "ATM WDL-" + hexid(8).upper(), digits(6), 15000.00, 0)]

wb = Workbook()
wb.remove(wb.active)
wb.properties.created = wb.properties.modified = datetime(2026, 3, 20)
for key in BANK_KEYS:
    e = E[key]
    entries = []
    for t in TXNS:
        if t["status"] != "SUCCESS":
            continue
        if t["payer"] is e:
            o = t["payee"]
            entries.append((t["ts"], f"UPI-{o['name'].upper()}-{o['vpa']}-{o['ifsc']}-{t['rrn']}-{t['remark'] or 'UPI'}",
                            t["rrn"], t["amount"], 0))
        elif t["payee"] is e:
            o = t["payer"]
            entries.append((t["ts"], f"UPI-{o['name'].upper()}-{o['vpa']}-{o['ifsc']}-{t['rrn']}-{t['remark'] or 'UPI'}",
                            t["rrn"], 0, t["amount"]))
    entries += [(ts.astimezone(UTC), n, r, dr, cr) for ts, n, r, dr, cr in EXTRAS[key]]
    entries.sort(key=lambda x: x[0])

    ws = wb.create_sheet(f"Acct_{e['acct']}")
    opening = OPENING.get(key, 150000.00)
    ws.append([f"STATEMENT OF ACCOUNT - {e['bank'].upper()}"])
    ws.append(["Account Name:", e["name"]])
    ws.append(["Account No:", e["acct"]])
    ws.append(["IFSC:", e["ifsc"]])
    ws.append(["Statement Period:", "13/03/2026 to 15/03/2026"])
    ws.append(["Opening Balance:", opening])
    ws.append([])
    ws.append(["Txn Date", "Value Date", "Narration", "Chq/Ref No", "Withdrawal Amt (Dr)", "Deposit Amt (Cr)", "Closing Balance"])
    for c in ws[8]:
        c.font = Font(bold=True)
    bal = opening
    for ts, narr, ref, dr, cr in entries:
        bal = round(bal - dr + cr, 2)
        ws.append([ist_str(ts, "%d/%m/%Y %H:%M:%S"), ist_str(ts, "%d/%m/%Y"), narr, ref,
                   dr or None, cr or None, bal])
    ws.append([])
    ws.append(["*** END OF STATEMENT ***"])
    for col, wd in zip("ABCDEFG", (20, 12, 70, 16, 20, 18, 16)):
        ws.column_dimensions[col].width = wd
wb.save(OUT / "bank_statement.xlsx")

# ----------------------------------------------------------------------------- 3) cdr.csv
CDR_COLS = ["CALLING_NO", "CALLED_NO", "CALL_TYPE", "SERVICE", "START_EPOCH", "DURATION_SEC", "IMEI", "IMSI",
            "FIRST_CELL_ID", "LAST_CELL_ID", "LAC", "TOWER_LAT", "TOWER_LON", "TOWER_ADDR"]
CDR = []


def fmt_phone(p):
    return rnd.choices([p, "+91" + p, "91" + p, "0" + p], [40, 30, 20, 10])[0]


def cdr_pair(a, b, start, dur, service="VOICE"):
    """A-party and B-party records (as if both numbers were requested)."""
    for me, ctype, jit in ((a, "MOC", 0), (b, "MTC", 1)):
        if service == "SMS":
            ctype = "SMS-MO" if ctype == "MOC" else "SMS-MT"
        first = me["cell"]
        last = first if rnd.random() > 0.15 else pick_tower(me["city"])
        tw = TOWERS[first]
        CDR.append({"ts": start + timedelta(seconds=jit), "calling": a["phone"], "called": b["phone"],
                    "type": ctype, "service": service, "dur": dur, "imei": me["imei"], "imsi": me["imsi"],
                    "first": first, "last": last, "tw": tw})


# scripted calls
cdr_pair(E["P1"], E["V"], at(14, 10, 5, 12), 840, "VOICE")
cdr_pair(E["P1"], E["V"], at(14, 10, 20, 5), 12420, "VIDEO")     # 3h27m00s
for fl in FLOWS:                                                   # handler -> mule, just before each forward
    for j in range(1, 7):
        cdr_pair(E["H1"], E[CHAIN[j]], fl["hop_times"][j] - timedelta(seconds=rnd.randint(90, 200)),
                 rnd.randint(20, 75), "VOICE")
# noise
for _ in range(170):
    a, b = rnd.sample(NOISE, 2)
    sms = rnd.random() < 0.15
    cdr_pair(a, b, rand_time(), 0 if sms else rnd.choice([0, rnd.randint(5, 900)]), "SMS" if sms else "VOICE")
for _ in range(6):                                                 # victim's normal life on 13-Mar
    n = rnd.choice(NOISE)
    cdr_pair(E["V"], n, rand_time(at(13, 7, 0), at(13, 21, 0)), rnd.randint(30, 600), "VOICE")

CDR.sort(key=lambda r: r["ts"])
hidden = rnd.sample(range(len(CDR)), 4)
with open(OUT / "cdr.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(CDR_COLS)
    for i, r in enumerate(CDR):
        calling = "" if (i in hidden and r["type"] == "MTC") else fmt_phone(r["calling"])  # hidden caller ID
        w.writerow([calling, fmt_phone(r["called"]), r["type"], r["service"], int(r["ts"].timestamp()),
                    r["dur"], r["imei"], r["imsi"], r["first"], r["last"], r["tw"]["lac"],
                    r["tw"]["lat"], r["tw"]["lon"], r["tw"]["addr"]])

# ----------------------------------------------------------------------------- 4) ipdr.csv
IPDR_COLS = ["MSISDN", "IMEI", "IMSI", "PRIVATE_IP", "PUBLIC_IP", "SRC_PORT", "DST_IP", "DST_PORT", "PROTOCOL",
             "START_TIME", "END_TIME", "UPLINK_BYTES", "DOWNLINK_BYTES", "APN", "CELL_ID"]
IPDR = []
RELAY_WA, RELAY_AD, RELAY_BANK = "203.0.113.45", "198.51.100.77", "192.0.2.10"   # RFC 5737 ranges


def ipdr_row(e, start, end, dst, dport, proto, up, down, pub_ip=None):
    IPDR.append([("91" + e["phone"]), e["imei"], e["imsi"], f"10.{rnd.randint(0, 255)}.{rnd.randint(0, 255)}.{rnd.randint(1, 254)}",
                 pub_ip or e["ip"], rnd.randint(30000, 65000), dst, dport, proto,
                 ist_str(start, "%d-%m-%Y %H:%M:%S"), ist_str(end, "%d-%m-%Y %H:%M:%S"), up, down, "jionet", e["cell"], start])


def chunked(e, start, end, dst, dport, proto, chunk_min, up_rate, down_rate, pub_ip=None):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(minutes=chunk_min), end)
        s = int((nxt - cur).total_seconds())
        ipdr_row(e, cur, nxt, dst, dport, proto, s * up_rate, s * down_rate, pub_ip)
        cur = nxt


call_start, call_end = at(14, 10, 20, 5), at(14, 13, 47, 5)
chunked(E["V"], call_start, call_end, RELAY_WA, 3478, "UDP", 30, 45000, 52000)        # victim side of video call
chunked(E["P1"], call_start + timedelta(seconds=1), call_end, RELAY_WA, 3478, "UDP", 30, 52000, 45000)
chunked(E["V"], at(14, 10, 31, 9), at(14, 13, 30, 0), RELAY_AD, 7070, "TCP", 60, 9000, 31000)  # AnyDesk
for fl in FLOWS:                                                                      # mule banking-app sessions
    for j in range(1, 7):
        t = fl["hop_times"][j]
        ipdr_row(E[CHAIN[j]], t - timedelta(seconds=60), t + timedelta(seconds=120), RELAY_BANK, 443, "TCP",
                 rnd.randint(8000, 40000), rnd.randint(40000, 200000))
for _ in range(90):
    e = rnd.choice(NOISE)
    s = rand_time()
    dur = rnd.randint(60, 2400)
    ipdr_row(e, s, s + timedelta(seconds=dur), rnd.choice(["192.0.2.", "198.51.100.", "203.0.113."]) + str(rnd.randint(100, 250)),
             rnd.choice([443, 443, 80, 5228]), "TCP", rnd.randint(2000, 900000), rnd.randint(10000, 9000000))
IPDR.sort(key=lambda r: r[-1])
with open(OUT / "ipdr.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(IPDR_COLS)
    w.writerows([r[:-1] for r in IPDR])

# ----------------------------------------------------------------------------- 5) device_dump.json
V, P1 = E["V"], E["P1"]


def cb(ts):  # Cellebrite-style display timestamp
    return ist_str(ts, "%d-%m-%Y %H:%M:%S") + "(UTC+5:30)"


vflow = [t for t in TXNS if t["tag"] in ("flow1_hop1", "flow2_hop1", "flow3_hop1")]
m1_vpa = E["M1"]["vpa"]
chat_script = [
    (at(14, 10, 2, 41), "IN", "Sir, this is Inspector Vikram Rathore, Cyber Crime Cell. Please answer the call. It is regarding a case against your Aadhaar."),
    (at(14, 10, 19, 50), "IN", "You are under digital arrest. Do not disconnect the video call or speak to anyone."),
    (at(14, 10, 29, 30), "IN", "Install AnyDesk from Play Store for verification of your devices. Share the 9-digit code."),
    (at(14, 10, 33, 12), "OUT", "Code: 481 276 905"),
    (at(14, 11, 8, 20), "IN", f"Transfer Rs 1,00,000 to RBI verification account: {m1_vpa}. It will be refunded after verification."),
    (at(14, 11, 13, 5), "OUT", "Done sir"),
    (at(14, 12, 3, 10), "IN", f"Second verification deposit Rs 1,00,000. Same account {m1_vpa}."),
    (at(14, 12, 6, 2), "OUT", "Done sir"),
    (at(14, 13, 8, 15), "IN", f"Final deposit Rs 90,000 to {m1_vpa}."),
    (at(14, 13, 11, 40), "OUT", "Done sir"),
    (at(14, 13, 47, 30), "IN", "Verification complete. Refund in 24 hours. Delete this chat."),
]
messages = [{"msg_id": f"WA-{i:04d}", "timestamp": cb(ts), "direction": "Incoming" if d == "IN" else "Outgoing",
             "from": P1["phone"] if d == "IN" else V["phone"], "to": V["phone"] if d == "IN" else P1["phone"],
             "body": body, "status": "Read" if d == "IN" else "Sent", "deleted": i == len(chat_script) - 1}
            for i, (ts, d, body) in enumerate(chat_script, 1)]
family = [{"msg_id": f"WA-F{i:03d}", "timestamp": cb(at(13, 19, 5 + i)), "direction": "Incoming" if i % 2 else "Outgoing",
           "from": "Mom", "to": V["phone"], "body": b, "status": "Read", "deleted": False}
          for i, b in enumerate(["Beta, are you free tomorrow?", "Yes, will call you in the evening", "Ok take care"], 1)]
sms = [{"sms_id": f"SMS-{i}", "timestamp": cb(t["ts"] + timedelta(seconds=3)), "sender": f"VM-{V['ifsc'][:4]}BK",
        "body": f"Rs.{t['amount']:,.2f} debited from a/c XX{V['acct'][-4:]} on {ist_str(t['ts'], '%d-%m-%y')} "
                f"to VPA {t['payee']['vpa']} (UPI Ref No {t['rrn']}). Not you? Report immediately."}
       for i, t in enumerate(vflow, 1)]
device = {
    "report_header": {
        "tool": "Cellebrite UFED (synthetic mimic)", "extraction_type": "Full File System",
        "case_number": "CYB/PUN/2026/0147", "examiner": "Synthetic Examiner, Cyber Lab",
        "extraction_start": cb(at(16, 11, 0)), "extraction_end": cb(at(16, 11, 42)),
        "device": {"model": "Samsung Galaxy A34 (SM-A346E)", "os": "Android 14", "imei": V["imei"],
                   "msisdn": "+91" + V["phone"], "owner": V["name"]},
    },
    "installed_applications": [
        {"name": "WhatsApp", "package": "com.whatsapp", "version": "2.24.8.76", "install_time": cb(at(1, 9, 0).replace(month=1)), "last_used": cb(at(14, 13, 47))},
        {"name": "AnyDesk", "package": "com.anydesk.anydeskandroid", "version": "8.0.9", "install_time": cb(at(14, 10, 31, 7)), "last_used": cb(at(14, 13, 30))},
        {"name": "Google Pay", "package": "com.google.android.apps.nbu.paisa.user", "version": "230.1", "install_time": cb(at(1, 9, 0).replace(year=2025)), "last_used": cb(at(14, 13, 11))},
        {"name": "Chrome", "package": "com.android.chrome", "version": "122.0", "install_time": cb(at(1, 9, 0).replace(year=2025)), "last_used": cb(at(14, 9, 40))},
    ],
    "chats": [
        {"chat_id": "WA-C1", "source_app": "WhatsApp", "participants": [V["phone"], P1["phone"]], "messages": messages},
        {"chat_id": "WA-C2", "source_app": "WhatsApp", "participants": [V["phone"], "Mom"], "messages": family},
    ],
    "sms_messages": sms,
    "call_log": [
        {"call_id": "CL-1", "timestamp": cb(at(14, 10, 5, 12)), "direction": "Incoming", "number": "+91" + P1["phone"], "duration_sec": 840, "type": "Voice"},
        {"call_id": "CL-2", "timestamp": cb(at(14, 10, 20, 5)), "direction": "Incoming", "number": "+91" + P1["phone"], "duration_sec": 12420, "type": "WhatsApp Video"},
    ],
    "contacts": [{"name": "Mom", "number": "+91" + rnd.choice(NOISE)["phone"]}, {"name": "Office", "number": "+91" + rnd.choice(NOISE)["phone"]}],
}
with open(OUT / "device_dump.json", "w", encoding="utf-8") as f:
    json.dump(device, f, indent=2, ensure_ascii=False)

# ----------------------------------------------------------------------------- ground truth
truth = {
    "warning": "ANSWER KEY - for Members 2/3/4 validation only. Never feed this to the parsers.",
    "entities": {k: {x: E[k][x] for x in ("name", "phone", "acct", "vpa", "ifsc", "imei", "device", "ip", "city")} for k in E},
    "chain": CHAIN,
    "shared_resources": {"entities": ["M3", "M5"], "imei": E["M3"]["imei"], "device_id": E["M3"]["device"], "public_ip": E["M3"]["ip"]},
    "mastermind_link": {"handler": "H1", "calls_each_mule_before_forwarding": True},
    "coercion_window_ist": {"video_call_start": ist_str(call_start, "%Y-%m-%d %H:%M:%S"),
                            "video_call_end": ist_str(call_end, "%Y-%m-%d %H:%M:%S"),
                            "anydesk_install": "2026-03-14 10:31:07"},
    "flows": [{"flow": f["flow"], "txn_ids": f["txn_ids"],
               "hop_times_utc": [t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") for t in f["hop_times"]]} for f in FLOWS],
    "expected_counts": {"upi_rows_in_file": len(upi_rows), "unique_txns": len(TXNS), "dup_rows": 3,
                        "corrupt_timestamp_rows": 2, "cdr_rows": len(CDR), "ipdr_rows": len(IPDR)},
}
with open(OUT / "ground_truth.json", "w", encoding="utf-8") as f:
    json.dump(truth, f, indent=2)

# ----------------------------------------------------------------------------- hash manifest
with open(OUT / "SHA256SUMS.txt", "w") as f:
    for p in sorted(OUT.iterdir()):
        if p.name != "SHA256SUMS.txt":
            f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")

print(f"Wrote synthetic dataset to {OUT}")
print(f"  upi_logs.csv        {len(upi_rows)} rows ({len(TXNS)} unique txns, 3 duplicates, 2 corrupt timestamps)")
print(f"  bank_statement.xlsx {len(BANK_KEYS)} account sheets")
print(f"  cdr.csv             {len(CDR)} rows")
print(f"  ipdr.csv            {len(IPDR)} rows")
print("  device_dump.json, ground_truth.json, SHA256SUMS.txt")
