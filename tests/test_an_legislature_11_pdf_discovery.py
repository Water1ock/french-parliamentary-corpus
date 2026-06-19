#!/usr/bin/env python3
"""
test_an_legislature_11_pdf_discovery.py

Verifies that Legislature XI PDF URLs follow the expected pattern:
  https://archives.assemblee-nationale.fr/11/cri/{session}/{numbered_pdf}.pdf

Why this test exists:
    Legislature XI (1997–2002) uses the archives subdomain with a simple
    numbered PDF scheme (001.pdf, 002.pdf, ...). This was discovered by
    probing the archives.assemblee-nationale.fr/11/cri/index.html page
    and extracting all session links, then testing whether numbered PDFs
    exist at the expected path.

What this test does:
    1. Scrapes a sample session index page for Legislature XI.
    2. Extracts all numbered PDF links.
    3. Downloads the first 5 PDFs and confirms they start with %PDF.
"""

import requests
from lxml import html
import re

requests.packages.urllib3.disable_warnings()

ARCHIVES = "https://archives.assemblee-nationale.fr"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}

# A representative session for Legislature XI
TEST_SESSION = "11-2000-2001-ordinaire1"


def test_discover_xi_pdfs():
    """Test that we can discover numbered PDFs from a XI session page."""
    url = f"{ARCHIVES}/11/cri/{TEST_SESSION}.html"
    r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
    assert r.status_code == 200, f"Session page returned {r.status_code}"

    tree = html.fromstring(r.content)
    links = tree.xpath("//a/@href")
    pdfs = [l for l in links if re.search(r'\d+\.pdf$', l)]

    assert len(pdfs) > 0, f"No numbered PDFs found in {TEST_SESSION}"
    print(f"Found {len(pdfs)} PDFs in {TEST_SESSION}")
    print(f"First PDF: {pdfs[0]}")


def test_xi_pdfs_are_valid():
    """Test that the first 5 discovered XI PDFs resolve to real PDF content."""
    # First, discover the PDFs
    url = f"{ARCHIVES}/11/cri/{TEST_SESSION}.html"
    r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
    assert r.status_code == 200

    tree = html.fromstring(r.content)
    links = tree.xpath("//a/@href")
    pdfs = [l for l in links if re.search(r'\d+\.pdf$', l)]

    # Test the first 5
    for pdf in pdfs[:5]:
        full_url = f"{ARCHIVES}/11/cri/{pdf}"
        r2 = requests.get(full_url, verify=False, timeout=30, headers=HEADERS)
        assert r2.status_code == 200, f"{full_url} returned {r2.status_code}"
        assert r2.content[:4] == b"%PDF", f"{full_url} is not a valid PDF"
        print(f"  ✅ {full_url}  ({len(r2.content):,} bytes)")


if __name__ == "__main__":
    test_discover_xi_pdfs()
    test_xi_pdfs_are_valid()
    print("\n✅ All Legislature XI tests passed.")
