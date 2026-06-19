#!/usr/bin/env python3
"""
test_coverage_gaps.py

Explores the Sénat site structure to understand what is and isn't accessible,
particularly around the 403 cutoff for older monthly indexes.

Why this test exists:
    The Sénat (French Senate) site structure has NOT yet been fully mapped.
    This test documents what we know so far: which monthly indexes are
    accessible, what session link patterns they use, and where the 403
    cutoff point falls. This serves as both a reference and a starting
    point for implementing the full Sénat URL discovery.

Current findings (preliminary):
    - Monthly index pattern: https://www.senat.fr/seances/s{YYYYMM}/
    - Newer indexes (≥2003) return 200
    - Older indexes (<2003) return 403
    - Session link patterns differ: newer use s{YYYYMMDD}.html,
      older use sc{YYYYMMDD}.html (but are behind the 403 wall)
    - The PDF URL derivation from session pages is not yet determined

What this test does:
    1. Probes monthly indexes at different dates to find the 403 cutoff
    2. Reads accessible indexes and reports session link patterns
    3. This information feeds into the eventual Sénat discovery implementation
"""

import re
import requests
from lxml import html

requests.packages.urllib3.disable_warnings()

SENATE = "https://www.senat.fr"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}

# Probe dates: early 2000s to find the cutoff
PROBE_DATES = [
    "200001", "200101", "200201", "200301",
    "200401", "200501", "200601", "202301",
]


def test_find_403_cutoff():
    """Probe monthly indexes to find where the 403 cutoff begins."""
    print("=== Finding accessible month range ===")
    for ym in PROBE_DATES:
        url = f"{SENATE}/seances/s{ym}/"
        r = requests.get(url, verify=False, timeout=10, headers=HEADERS)
        status_str = "✅ ACCESSIBLE" if r.status_code == 200 else f"❌ {r.status_code}"
        print(f"  {status_str}  /seances/s{ym}/")

    # Check 2000-2002 systematically
    print("\n--- Systematic check: 2000-2002 ---")
    for year in range(2000, 2003):
        for month in range(1, 13):
            ym = f"{year}{month:02d}"
            url = f"{SENATE}/seances/s{ym}/"
            r = requests.get(url, verify=False, timeout=10, headers=HEADERS)
            if r.status_code == 200:
                print(f"  ✅  /seances/s{ym}/  (accessible)")
            elif r.status_code == 403:
                pass  # Suppress 403s for brevity, just note the first
        # Print first 403 per year
        for month in range(1, 13):
            ym = f"{year}{month:02d}"
            url = f"{SENATE}/seances/s{ym}/"
            r = requests.get(url, verify=False, timeout=10, headers=HEADERS)
            if r.status_code == 403:
                print(f"  First 403:  /seances/s{ym}/  (earliest blocked in {year})")
                break


def test_accessible_index_patterns():
    """Read accessible monthly indexes and report session link patterns."""
    print("\n=== Accessible index patterns ===")
    for ym in ["200301", "200501", "202301"]:
        url = f"{SENATE}/seances/s{ym}/"
        r = requests.get(url, verify=False, timeout=15, headers=HEADERS)
        if r.status_code != 200:
            continue
        tree = html.fromstring(r.content)
        links = tree.xpath("//a/@href")
        session_links = sorted(set(
            l for l in links
            if re.search(r's\d{8}', l)
        ))
        print(f"\n  /seances/s{ym}/  ({len(session_links)} session links)")
        if session_links:
            for l in session_links[:5]:
                print(f"    {l}")
            if len(session_links) > 5:
                print(f"    ... and {len(session_links)-5} more")


def test_senate_pdf_url_unknown():
    """
    Placeholder: Sénat PDF URL pattern is not yet determined.

    Once the session page structure is understood, this test will verify
    the derived PDF URL pattern.
    """
    print("\n⚠️  Sénat PDF URL pattern is NOT YET DETERMINED.")
    print("   This test will be implemented once the Sénat site structure is mapped.")


if __name__ == "__main__":
    test_find_403_cutoff()
    test_accessible_index_patterns()
    test_senate_pdf_url_unknown()
    print("\n✅ Coverage gaps documented. See STATUS.md for open issues.")
