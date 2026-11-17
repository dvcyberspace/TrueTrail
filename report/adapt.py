# report/adapt.py
"""Bridge: synthetic data .csv file with Lead objects.

Reads: entities.csv, links.csv, events.csv  (all under evidence_data/)
Produces: 4 leads, one per target entity in links.csv (E04, E05, E06, E08).
E04 is the hero lead (most incoming links + most events).
"""
from pathlib import Path
import pandas as pd

from report.lead_pack import Lead, Evidence, _norm_confidence, _lead_id
from report.audit import sha256_file

DATA_DIR = Path("data")

ENTITY_LABELS = {
    "E01": "Priya Patel (Victim)",
    "E02": "Rahul Kumar (Victim)",
    "E03": "Amit Sharma (Victim)",
    "E04": "Sunil Verma (Mule M1)",
    "E05": "Onward Acct A",
    "E06": "Onward Acct B",
    "E07": "Recruiter Target",
    "E08": "ATM Cash Out Point",
}


def _evidence(source_doc: str, snippet: str, cache: dict[str, str]) -> Evidence:
    if source_doc not in cache:
        cache[source_doc] = sha256_file(str(DATA_DIR / source_doc))
    return Evidence(source_doc=source_doc, sha256=cache[source_doc], snippet=snippet)


def leads_from_links() -> list[Lead]:
    """One lead per unique target entity in links.csv."""
    cache: dict[str, str] = {}
    links = pd.read_csv(DATA_DIR / "links.csv")
    ents = pd.read_csv(DATA_DIR / "entities.csv").set_index("entity_id")

    by_target: dict[str, list] = {}
    for _, row in links.iterrows():
        by_target.setdefault(row["target_entity_id"], []).append(row)

    leads: list[Lead] = []
    for target, rows in by_target.items():
        sources = sorted({r["source_entity_id"] for r in rows})
        ids = sorted(set(sources + [target]))
        conf = max(float(r["strength_score"]) for r in rows)
        rels = sorted({r["relationship_type"] for r in rows})
        tgt_lbl = ents.loc[target, "name"] if target in ents.index else target
        src_lbls = ", ".join(ENTITY_LABELS.get(s, s) for s in sources)

        leads.append(Lead(
            lead_id=_lead_id(ids),
            title=f"{tgt_lbl} — {len(rows)} incoming link(s)",
            summary=(
                f"{tgt_lbl} ({target}) receives {len(rows)} link(s): "
                f"{', '.join(rels)}. Sources: {src_lbls}."
            ),
            confidence=_norm_confidence(conf),
            entities=ids,
            evidence=[
                _evidence(
                    "links.csv",
                    f"{r['source_entity_id']}->{r['target_entity_id']} "
                    f"({r['relationship_type']}, {r['strength_score']})",
                    cache,
                )
                for r in rows
            ],
        ))
    return leads


def enrich_with_events(lead: Lead) -> Lead:
    cache = {e.source_doc: e.sha256 for e in lead.evidence}
    evs = pd.read_csv(DATA_DIR / "events.csv")
    matching = evs[evs["true_entity_id"].isin(lead.entities)]
    for _, ev in matching.iterrows():
        lead.evidence.append(_evidence(
            "events.csv",
            f"{ev['event_id']} {ev['event_type']}: {ev['details']}",
            cache,
        ))
    return lead


def all_leads() -> list[Lead]:
    return [enrich_with_events(l) for l in leads_from_links()]


def hero_lead(leads: list[Lead]) -> Lead:
    return max(leads, key=lambda l: len(l.evidence))


# test
if __name__ == "__main__":
    from report.audit import hash_all_evidence

    print("=== Evidence files hashed ===")
    for name, h in hash_all_evidence().items():
        print(f"  {name:<30} {h[:16]}…")

    leads = all_leads()
    print(f"\n=== {len(leads)} leads produced ===")
    for l in leads:
        print(f"\n  {l.lead_id}  conf={l.confidence:.2f}  evidence={len(l.evidence)}")
        print(f"  {l.title}")
        print(f"  {l.summary}")
        for e in l.evidence[:3]:
            print(f"     · {e.source_doc}: {e.snippet[:70]}")

    h = hero_lead(leads)
    print(f"\n=== HERO LEAD: {h.lead_id} — {h.title} ===")