#!/usr/bin/env python3
"""
test_an_legislature_12_14_pdf_url_pattern.py

Verifies that Legislature XII–XIV PDF URLs are correctly derived from
session .asp filenames via the pattern:
  /{leg}/cri/{session}/{YYYYMMDD}.asp  →  /{leg}/pdf/cri/{session}/{YYYYMMDD}.pdf

Why this test exists:
    For legislatures XII (2002–2007), XIII (2007–2012), and XIV (2012–2017),
    the AN site lists session indices as .asp files named by date (e.g.
    20021002.asp). Direct directory listing at /{leg}/cri/{session}/ returns
    403, but the index pages are readable. The PDF URL is derived by moving
    from /cri/ to /pdf/cri/ and changing .asp to .pdf. This test confirms
    the derivation produces real PDF content for a sample of sessions.

What this test does:
    1. For each legislature (12, 13, 14), selects a representative session.
    2. Scrapes its .asp index page.
    3. Extracts the first 3 date codes.
    4. Derives the PDF URLs and confirms they return application/pdf content.
"""

import re
import requests
from lxml import html

requests.packages.urllib3.disable_warnings()

BASE = "https://www.assemblee-nationale.fr"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}

SAMPLE_SESSIONS = {
    12: "2002-2003",
    13: "2007-2008",
    14: "2012-2013",
}


def test_session_index_is_readable():
    """Test that session index pages for XII–XIV return 200."""
    for leg, sess in SAMPLE_SESSIONS.items():
        url = f"{BASE}/{leg}/cri/{sess}/"
        r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
        assert r.status_code == 200, f"{url} returned {r.status_code}"
        print(f"  ✅ Legislature {leg} session {sess}: {r.status_code}")


def test_derive_pdf_urls():
    """Test that derived PDF URLs resolve to valid PDF content."""
    for leg, sess in SAMPLE_SESSIONS.items():
        url = f"{BASE}/{leg}/cri/{sess}/"
        r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
        assert r.status_code == 200

        tree = html.fromstring(r.content)
        links = tree.xpath("//a/@href")
        dates = set()
        for l in links:
            m = re.match(r'(\d{8})\.asp', l)
            if m:
                dates.add(m.group(1))

        assert len(dates) > 0, f"No .asp links found for legislature {leg} session {sess}"
        print(f"\n  Legislature {leg} ({sess}): {len(dates)} dates found")

        for d in sorted(dates)[:3]:
            pdf_url = f"{BASE}/{leg}/pdf/cri/{sess}/{d}.pdf"
            r2 = requests.get(pdf_url, verify=False, timeout=30, headers=HEADERS)
            assert r2.status_code == 200, f"{pdf_url} returned {r2.status_code}"
            assert r2.content[:4] == b"%PDF", f"{pdf_url} is not a valid PDF"
            print(f"    ✅ {d}.pdf  ({len(r2.content):,} bytes)")


def test_no_asp_leak_into_pdf_urls():
    """Test that .asp files are NOT used directly as PDF URLs — they must be .pdf."""
    for leg, sess in SAMPLE_SESSIONS.items():
        url = f"{BASE}/{leg}/cri/{sess}/"
        r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
        assert r.status_code == 200

        tree = html.fromstring(r.content)
        links = tree.xpath("//a/@href")
        asp_links = [l for l in links if l.endswith(".asp")]
        pdf_links = [l for l in links if l.endswith(".pdf")]

        # Index pages should have .asp links, not .pdf links
        # (PDFs are at /pdf/cri/, not /cri/)
        assert len(asp_links) > 0, f"No .asp links found for leg {leg}"
        assert len(pdf_links) == 0, (
            f"Found {len(pdf_links)} direct .pdf links in /cri/ index "
            f"(expected 0 — PDFs are at /pdf/cri/)"
        )


if __name__ == "__main__":
    test_session_index_is_readable()
    test_derive_pdf_urls()
    test_no_asp_leak_into_pdf_urls()
    print("\n✅ All Legislature XII–XIV tests passed.")
