from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime
import os

def generate_report(file_name, file_hash, case_id, io_name):
    os.makedirs("../evidence_pack", exist_ok=True)
    pdf_path = f"../evidence_pack/BSA_Certificate_{case_id}.pdf"
    
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    
    # Header
    c.setFillColor(colors.HexColor("#1a237e"))
    c.rect(0, height - 80, width, 80, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "CERTIFICATE OF ELECTRONIC EVIDENCE")
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 110, "Under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023")
    
    # Body
    c.setFont("Helvetica", 11)
    text_lines = [
        f"Case ID: {case_id}",
        f"Date of Generation: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}",
        f"Investigating Officer: {io_name}",
        "",
        "1. DESCRIPTION OF ELECTRONIC RECORD:",
        f"   File Name: {file_name}",
        f"   Hash Algorithm: SHA-256",
        f"   Cryptographic Hash: {file_hash}",
        "",
        "2. CERTIFICATION:",
        "   I hereby certify that the electronic record described above",
        "   was produced by the computer/device during the period over",
        "   which the computer/device was used regularly. The integrity",
        "   of this record has been maintained via cryptographic hash",
        "   verification at the time of ingestion.",
        "",
        "3. CHAIN OF CUSTODY:",
        "   This document is linked to a hash-chained SQLite ledger.",
        "   Any modification to the original file will result in a",
        "   hash mismatch, invalidating this certificate.",
    ]
    
    y = height - 140
    for line in text_lines:
        c.drawString(50, y, line)
        y -= 18
        
    # Signature
    c.line(50, y - 40, 250, y - 40)
    c.drawString(50, y - 55, "Signature of Investigating Officer")
    
    c.save()
    return pdf_path