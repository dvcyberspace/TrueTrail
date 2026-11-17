import os
import json
import pandas as pd

os.makedirs("evidence_data", exist_ok=True)

# Bank / UPI transaction evidence
bank_data = {
    "transaction_id": ["TXN001", "TXN002", "TXN003", "TXN004", "TXN005"],
    "timestamp": [
        "2023-10-25 10:15:00",
        "2023-10-25 11:20:00",
        "2023-10-25 14:05:00",
        "2023-10-26 09:30:00",
        "2023-10-26 16:45:00"
    ],
    "sender_name": [
        "Amit Sharma",
        "Rajesh Kumar",
        "Amit S.",
        "Priya Patel",
        "Unknown Sender"
    ],
    "receiver_name": [
        "Kirana Store",
        "Amit Sharma",
        "Paytm-Vendor-99",
        "Rajesh Kumar",
        "Amit Sharma"
    ],
    "amount": [15000.00, 5000.00, 1250.00, 50000.00, 100000.00],
    "status": ["SUCCESS", "SUCCESS", "FAILED", "SUCCESS", "SUCCESS"],
    "payment_mode": ["UPI", "IMPS", "UPI", "NEFT", "UPI"]
}

pd.DataFrame(bank_data).to_csv(
    "evidence_data/bank_upi_transactions.csv",
    index=False
)

# Chat evidence
chat_export = [
    {
        "sender": "Amit Sharma",
        "timestamp": "2023-10-25T10:12:00Z",
        "message": "I am sending the payment of ₹15000 now.",
        "channel": "WhatsApp"
    },
    {
        "sender": "Rajesh Kumar",
        "timestamp": "2023-10-25T11:18:00Z",
        "message": "Received. Sending back your ₹5000 change.",
        "channel": "WhatsApp"
    },
    {
        "sender": "Priya",
        "timestamp": "2023-10-26T09:28:00Z",
        "message": "Can you transfer the budget to Rajesh?",
        "channel": "Telegram"
    }
]

with open("evidence_data/chat_export.json", "w", encoding="utf-8") as file:
    json.dump(chat_export, file, indent=2)

# IP login evidence
ip_data = {
    "log_id": [101, 102, 103, 104],
    "timestamp": [
        "2023-10-25 10:14:55",
        "2023-10-25 11:19:40",
        "2023-10-25 14:04:10",
        "2023-10-26 09:29:15"
    ],
    "username": ["amit_s", "rkumar", "amit_s", "ppatel"],
    "ip_address": [
        "103.241.12.45",
        "115.240.99.12",
        "103.241.12.45",
        "117.200.45.89"
    ],
    "device_os": ["Android", "Windows", "Android", "macOS"]
}

pd.DataFrame(ip_data).to_csv(
    "evidence_data/ip_logs.csv",
    index=False
)

# CCTV evidence
cctv_data = {
    "camera_id": ["CAM-01", "CAM-02", "CAM-01", "CAM-03"],
    "timestamp": [
        "2023-10-25 10:13:00",
        "2023-10-25 11:21:00",
        "2023-10-25 14:06:00",
        "2023-10-26 16:44:00"
    ],
    "location": [
        "Main Entrance",
        "Back Alley",
        "Main Entrance",
        "Lobby"
    ],
    "detected_activity": [
        "Person Entry",
        "Person Exit",
        "Person Entry",
        "Loitering"
    ],
    "confidence_score": [0.95, 0.88, 0.92, 0.75]
}

pd.DataFrame(cctv_data).to_csv(
    "evidence_data/cctv_metadata.csv",
    index=False
)

print("Sample evidence files created in evidence_data folder")

for filename in os.listdir("evidence_data"):
    print("-", filename)