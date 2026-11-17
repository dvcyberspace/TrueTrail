# demo/mock_leads.py
"""Fallback leads so the demo can never break. Ids match the real algorithm."""
from report.lead_pack import Lead, Evidence, _lead_id

FAKE = "0" * 64   # placeholder hash; real adapt.py uses real sha256

# Same sorted entity id sets that report/adapt.py produces from links.csv:
_L_E04 = _lead_id(["E01", "E02", "E03", "E04", "E07"])   # hero
_L_E08 = _lead_id(["E04", "E08"])                         # cash-out

MOCK_LEADS = [
    Lead(
        lead_id=_L_E04,
        title="Sunil Verma (Mule M1) — 4 incoming links",
        summary=(
            "E01, E02, E03 (victims) and E07 (recruiter) all link to E04. "
            "E04 forwards to E05, E06, E08."
        ),
        confidence=0.92,
        entities=["E01", "E02", "E03", "E04", "E07"],
        evidence=[
            Evidence("links.csv", FAKE, "E01->E04 Victim_To_Mule 0.90"),
            Evidence("links.csv", FAKE, "E02->E04 Victim_To_Mule 0.85"),
            Evidence("links.csv", FAKE, "E03->E04 Victim_To_Mule 0.92"),
            Evidence("links.csv", FAKE, "E07->E04 Recruiter_To_Mule 0.80"),
            Evidence("events.csv", FAKE, "EVT_004 Device Login: DEV-SH99"),
            Evidence("events.csv", FAKE, "EVT_009 ATM Access Log: INR 15000"),
        ],
    ),
    Lead(
        lead_id=_L_E08,
        title="ATM Cash Out Point — E04 withdrawal",
        summary="E04 links directly to ATM E08; ATM withdrawal of INR 15000.",
        confidence=0.99,
        entities=["E04", "E08"],
        evidence=[
            Evidence("links.csv", FAKE, "E04->E08 Mule_To_Cashout 0.99"),
            Evidence("events.csv", FAKE, "EVT_009 ATM withdrawal INR 15000"),
        ],
    ),
]