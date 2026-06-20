#!/usr/bin/env python3
"""
Quick script: Download all Senat PDFs from data/senat_inventory.csv.
Run from the project root:

    python download_senat_pdfs.py

Resume-safe: skips already-downloaded files.
Rate-limited: 0.5s delay between requests.
Only downloads PDF-era URLs (2008-2025, ~2,178 files).
HTML-era sessions (2003-2007) are skipped automatically.
"""
import csv
import time
from pathlib import Path

import requests

requests.packages.urllib3.disable_warnings()

INVENTORY = Path("data/senat_inventory.csv")
PDF_DIR = Path("data/pdfs")
ERRORS = Path("data/senat_download_errors.csv")
DELAY = 0.5
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}

PDF_DIR.mkdir(parents=True, exist_ok=True)

def main():
    if not INVENTORY.exists():
        print(f"ERROR: {INVENTORY} not found. Run inventory/build_senat_url_inventory.py first.")
        return

    with open(INVENTORY, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Only download PDF-era sessions (URLs ending in .pdf)
    pdf_rows = [r for r in rows if r["url"].endswith(".pdf")]
    print(f"Total PDF-era sessions: {len(pdf_rows)}")
    print(f"HTML-era sessions (skipped): {len(rows) - len(pdf_rows)}")

    # Count already downloaded
    done = sum(1 for r in pdf_rows if Path(PDF_DIR, f"S_{Path(r['url']).name}").exists())
    print(f"Already downloaded: {done}")
    print(f"Remaining: {len(pdf_rows) - done}\n")

    errors = []
    downloaded = 0

    for i, row in enumerate(pdf_rows):
        url = row["url"]
        filename = f"S_{Path(url).name}"
        filepath = PDF_DIR / filename

        if filepath.exists():
            continue

        try:
            r = requests.get(url, headers=HEADERS, verify=False, timeout=60)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                filepath.write_bytes(r.content)
                downloaded += 1
                if downloaded % 50 == 0:
                    print(f"  [{i+1}/{len(pdf_rows)}] Downloaded {downloaded} new PDFs...")
            else:
                errors.append({**row, "status": r.status_code, "reason": "not a PDF"})
                print(f"  SKIP {r.status_code} {url}")

            time.sleep(DELAY)
        except Exception as e:
            errors.append({**row, "status": "ERR", "reason": str(e)})
            print(f"  ERR {url}: {e}")

    # Write errors
    with open(ERRORS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["legislature", "session", "url", "status", "reason"])
        writer.writeheader()
        writer.writerows(errors)

    print(f"\nDone. {downloaded} new PDFs downloaded.")
    print(f"Errors: {len(errors)} (see {ERRORS})")
    print(f"Total on disk: {len(list(PDF_DIR.glob('*.pdf')))}")

if __name__ == "__main__":
    main()
