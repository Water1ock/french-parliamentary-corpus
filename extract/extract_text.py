#!/usr/bin/env python3
"""
extract_text.py — Extract structured text from downloaded debate PDFs.

TODO: This module is a STUB. The PDF text extraction logic has not yet been
implemented. Once written, it should:

    1. Read the PDF inventory (data/pdf_inventory.csv) to know which sessions exist.
    2. For each downloaded PDF in data/pdfs/, extract the raw text using
       a library like pdfplumber or PyMuPDF (fitz).
    3. Parse the extracted text into structured fields:
       - speaker_name    (e.g. "DUPONT Jean")
       - speaker_party   (e.g. "LR", "PS", "RN")
       - speech          (the utterance text)
       - debate_title    (the agenda item / topic under discussion)
       - date            (session date, YYYY-MM-DD)
       - legislature     (11–17)
       - chamber         ("assemblee_nationale")
       - session_type    ("ordinaire" or "extraordinaire")
       - speaker_role    ("président", "ministre", "député", etc.)
    4. Output a structured CSV/Parquet table to data/extracted/

The main challenge here is that AN PDFs come in TWO formats depending on era:

    A) Older PDFs (XI–XIV): scanned images with hidden text layers.
       These may require OCR (Tesseract) as a fallback.
    B) Newer PDFs (XV–XVII): born-digital PDFs with selectable text.
       These can be parsed with pdfplumber directly.

The text layout also varies between legislatures, so per-legislature
parsing strategies may be needed.

Design principles for the eventual implementation:
    - Process one PDF at a time to keep memory manageable.
    - Write incremental CSV output (one row per speech) so partial results
      are never lost if the process is interrupted.
    - Log the number of speeches extracted per file for coverage tracking.
    - Flag PDFs where parsing produced suspiciously few or no speeches.

Usage (when implemented):
    python extract/extract_text.py

Status: 🔴 STUB — NOT IMPLEMENTED
"""

if __name__ == "__main__":
    print("❌ extract_text.py is a stub — not yet implemented.")
    print("   See STATUS.md for current status and priorities.")
