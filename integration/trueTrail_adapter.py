import json
import os
import pandas as pd


TRUE_TRAIL_DATA = r"C:\Users\jayap\Documents\project work\TrueTrail\data\canonical"
OUTPUT_DATA = "data"


os.makedirs(OUTPUT_DATA, exist_ok=True)


def load_json(filename):
    path = os.path.join(TRUE_TRAIL_DATA, filename)

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def add_entity(rows, entity_id, entity_type, role="unknown"):
    entity_id = clean(entity_id)

    if not entity_id:
        return

    rows.append({
        "entity_id": entity_id,
        "label": entity_id,
        "type": entity_type,
        "role": role,
        "value": entity_id
    })


def create_entities(transactions, calls, ip_sessions):
    rows = []

    for transaction in transactions:
        if clean(transaction.get("status", "")).upper() != "SUCCESS":
            continue

        add_entity(rows, transaction.get("sender_account"), "account")
        add_entity(rows, transaction.get("receiver_account"), "account")
        add_entity(rows, transaction.get("sender_vpa"), "vpa")
        add_entity(rows, transaction.get("receiver_vpa"), "vpa")
        add_entity(rows, transaction.get("sender_mobile"), "phone")
        add_entity(rows, transaction.get("device_id"), "device")
        add_entity(rows, transaction.get("ip_address"), "ip_address")

    for call in calls:
        add_entity(rows, call.get("caller"), "phone")
        add_entity(rows, call.get("callee"), "phone")
        add_entity(rows, call.get("target_number"), "phone")
        add_entity(rows, call.get("imei"), "device")

    for session in ip_sessions:
        add_entity(rows, session.get("msisdn"), "phone")
        add_entity(rows, session.get("src_ip"), "ip_address")
        add_entity(rows, session.get("imei"), "device")

    entities = pd.DataFrame(rows)

    if entities.empty:
        return entities

    return entities.drop_duplicates(subset=["entity_id"])


def create_transactions(transactions):
    rows = []

    for transaction in transactions:
        if clean(transaction.get("status", "")).upper() != "SUCCESS":
            continue

        sender = (
            clean(transaction.get("sender_account"))
            or clean(transaction.get("sender_vpa"))
        )

        receiver = (
            clean(transaction.get("receiver_account"))
            or clean(transaction.get("receiver_vpa"))
        )

        if not sender or not receiver:
            continue

        rows.append({
            "transaction_id": transaction.get("txn_id"),
            "from_acct": sender,
            "to_acct": receiver,
            "amount": transaction.get("amount", 0),
            "timestamp": transaction.get("timestamp"),
            "channel": transaction.get("channel", "UNKNOWN")
        })

    return pd.DataFrame(rows)


def create_events(transactions, calls, ip_sessions):
    rows = []

    for transaction in transactions:
        if clean(transaction.get("status", "")).upper() != "SUCCESS":
            continue

        entity_id = (
            clean(transaction.get("sender_account"))
            or clean(transaction.get("sender_vpa"))
        )

        if not entity_id:
            continue

        rows.append({
            "event_id": transaction.get("txn_id"),
            "entity_id": entity_id,
            "timestamp": transaction.get("timestamp"),
            "type": "TRANSACTION",
            "description": (
                f"{transaction.get('channel', 'Transaction')} transaction "
                f"of INR {transaction.get('amount', 0)}"
            ),
            "source_doc": transaction.get("source_file"),
            "location": ""
        })

    for call in calls:
        entity_id = clean(call.get("target_number"))

        if not entity_id:
            continue

        rows.append({
            "event_id": call.get("record_id"),
            "entity_id": entity_id,
            "timestamp": call.get("start_time"),
            "type": "CALL",
            "description": (
                f"{call.get('direction')} {call.get('call_type')} call"
            ),
            "source_doc": call.get("source_file"),
            "location": call.get("tower_address")
        })

    for session in ip_sessions:
        entity_id = clean(session.get("msisdn"))

        if not entity_id:
            continue

        rows.append({
            "event_id": session.get("session_id"),
            "entity_id": entity_id,
            "timestamp": session.get("start_time"),
            "type": "IP_SESSION",
            "description": (
                f"IP session from {session.get('src_ip')} "
                f"using {session.get('app_hint', 'unknown app')}"
            ),
            "source_doc": session.get("source_file"),
            "location": ""
        })

    return pd.DataFrame(rows)


def create_links(transactions, calls, ip_sessions):
    rows = []

    for transaction in transactions:
        if clean(transaction.get("status", "")).upper() != "SUCCESS":
            continue

        sender_account = clean(transaction.get("sender_account"))
        sender_vpa = clean(transaction.get("sender_vpa"))
        receiver_account = clean(transaction.get("receiver_account"))
        receiver_vpa = clean(transaction.get("receiver_vpa"))
        sender_mobile = clean(transaction.get("sender_mobile"))
        device_id = clean(transaction.get("device_id"))
        ip_address = clean(transaction.get("ip_address"))
        txn_id = transaction.get("txn_id")

        if sender_account and sender_vpa:
            rows.append({
                "entity_a": sender_account,
                "entity_b": sender_vpa,
                "link_type": "account_vpa_link",
                "evidence_ref": txn_id
            })

        if receiver_account and receiver_vpa:
            rows.append({
                "entity_a": receiver_account,
                "entity_b": receiver_vpa,
                "link_type": "account_vpa_link",
                "evidence_ref": txn_id
            })

        if sender_mobile:
            if sender_account:
                rows.append({
                    "entity_a": sender_mobile,
                    "entity_b": sender_account,
                    "link_type": "phone_account_link",
                    "evidence_ref": txn_id
                })

            if sender_vpa:
                rows.append({
                    "entity_a": sender_mobile,
                    "entity_b": sender_vpa,
                    "link_type": "phone_vpa_link",
                    "evidence_ref": txn_id
                })

        if device_id:
            for account in [sender_account, sender_vpa, receiver_account, receiver_vpa]:
                if account:
                    rows.append({
                        "entity_a": device_id,
                        "entity_b": account,
                        "link_type": "shared_device",
                        "evidence_ref": txn_id
                    })

        if ip_address:
            for account in [sender_account, sender_vpa, receiver_account, receiver_vpa]:
                if account:
                    rows.append({
                        "entity_a": ip_address,
                        "entity_b": account,
                        "link_type": "shared_ip",
                        "evidence_ref": txn_id
                    })

    for call in calls:
        phone = clean(call.get("target_number"))
        imei = clean(call.get("imei"))
        record_id = call.get("record_id")

        if phone and imei:
            rows.append({
                "entity_a": phone,
                "entity_b": imei,
                "link_type": "phone_device_link",
                "evidence_ref": record_id
            })

    for session in ip_sessions:
        phone = clean(session.get("msisdn"))
        ip_address = clean(session.get("src_ip"))
        imei = clean(session.get("imei"))
        session_id = session.get("session_id")

        if phone and ip_address:
            rows.append({
                "entity_a": phone,
                "entity_b": ip_address,
                "link_type": "phone_ip_link",
                "evidence_ref": session_id
            })

        if phone and imei:
            rows.append({
                "entity_a": phone,
                "entity_b": imei,
                "link_type": "phone_device_link",
                "evidence_ref": session_id
            })

    return pd.DataFrame(rows)

def extract_records(data):
    if isinstance(data, dict):
        if "items" in data:
            return data["items"]

        for value in data.values():
            if isinstance(value, list):
                return value

        return []

    return data
def main():
    transactions = extract_records(load_json("transactions.json"))
    calls = extract_records(load_json("calls.json"))
    ip_sessions = extract_records(load_json("ip_sessions.json"))

    print(f"Loaded transactions: {len(transactions)}")
    print(f"Loaded calls: {len(calls)}")
    print(f"Loaded IP sessions: {len(ip_sessions)}")
    entities = create_entities(
        transactions,
        calls,
        ip_sessions
    )

    transaction_rows = create_transactions(transactions)
    event_rows = create_events(
        transactions,
        calls,
        ip_sessions
    )

    link_rows = create_links(
        transactions,
        calls,
        ip_sessions
    )

    entities.to_csv(
        os.path.join(OUTPUT_DATA, "entities.csv"),
        index=False
    )

    transaction_rows.to_csv(
        os.path.join(OUTPUT_DATA, "transactions.csv"),
        index=False
    )

    event_rows.to_csv(
        os.path.join(OUTPUT_DATA, "events.csv"),
        index=False
    )

    link_rows.to_csv(
        os.path.join(OUTPUT_DATA, "links.csv"),
        index=False
    )

    print("TrueTrail data converted successfully.")
    print(f"Entities: {len(entities)}")
    print(f"Successful transactions: {len(transaction_rows)}")
    print(f"Events: {len(event_rows)}")
    print(f"Links: {len(link_rows)}")


if __name__ == "__main__":
    main()