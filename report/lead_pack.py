"""Lead card model + Markdown/PDF export. Consumed by C's Streamlit UI."""
from dataclasses import dataclass, field, asdict
from typing import List
import hashlib


@dataclass
class Evidence:
    source_doc: str        # e.g. "links.csv"
    sha256: str            
    snippet: str = ""      


@dataclass
class Lead:
    lead_id: str
    title: str
    summary: str
    confidence: float      # 0.0–1.0
    entities: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    status: str = "pending"    # pending | accepted | rejected
    notes: str = ""


def _norm_confidence(c) -> float:
    """Normalize B's score into 0.0–1.0. Handles float, 0-100, or label."""
    if isinstance(c, str):
        return {"high": 0.85, "medium": 0.6, "low": 0.35}.get(c.lower(), 0.5)
    c = float(c)
    return c / 100 if c > 1 else c


def _lead_id(entity_ids: list[str]) -> str:
    """Stable id from sorted entity ids. Same input -> same id, always."""
    key = ",".join(sorted(entity_ids))
    return "L-" + hashlib.sha1(key.encode()).hexdigest()[:6]


def to_markdown(lead: Lead) -> str:
    lines = [
        f"# {lead.title}",
        "",
        f"**Lead ID:** `{lead.lead_id}`  ",
        f"**Status:** {lead.status}  ",
        f"**Confidence:** {lead.confidence:.0%}",
        "",
        "## Summary",
        lead.summary,
        "",
        "## Linked entities",
        ", ".join(lead.entities) or "—",
        "",
        "## Evidence",
    ]
    for e in lead.evidence:
        lines.append(
            f"- `{e.source_doc}` · sha256 `{e.sha256[:16]}…` — {e.snippet}"
        )
    if lead.notes:
        lines += ["", "## Analyst notes", lead.notes]
    return "\n".join(lines)


def to_pdf(lead: Lead, out_path: str) -> None:
    """Requires: pip install fpdf2 (import name is fpdf)."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, lead.title)
    pdf.set_font("Helvetica", size=11)
    header = (
        f"Lead {lead.lead_id} | {lead.status} | confidence {lead.confidence:.0%}\n\n"
        f"{lead.summary}"
    )
    pdf.multi_cell(0, 6, header)
    pdf.ln(4)
    for e in lead.evidence:
        pdf.multi_cell(
            0, 5,
            f"- {e.source_doc} (sha256 {e.sha256[:16]}...): {e.snippet}",
        )
    pdf.output(out_path)