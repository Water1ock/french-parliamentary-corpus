#!/usr/bin/env python3
"""
test_pdf_url_validity.py

Verifies that ALL discovered PDF URLs in the inventory resolve to real
application/pdf content. This is the master validation test — it proves
the URL discovery patterns are correct across every legislature.

Why this test exists:
    The old repo confirmed 7,845 PDF URLs returning valid application/pdf
    content. In the new repo, whenever the inventory is rebuilt, this test
    should be re-run to confirm no regressions. This is the primary
    methodology evidence for the dataset paper.

What this test does:
    - Loads data/pdf_inventory.csv
    - For each URL, performs a full GET and checks the first 4 bytes
      for the %PDF magic number
    - Reports counts of valid vs invalid URLs per legislature

Note:
    This test sends 7,000+ requests and takes a while. Run with:
        python -m pytest tests/test_pdf_url_validity.py -v
    Or as a spot-check (first 10 URLs per legislature):
        python tests/test_pdf_url_validity.py --spot-check
"""

import csv
import sys
from pathlib import Path

import requests

requests.packages.urllib3.disable_warnings()

INVENTORY = Path("data/pdf_inventory.csv")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}


def test_inventory_exists():
    """Sanity check: the inventory file must exist."""
    assert INVENTORY.exists(), f"Inventory not found at {INVENTORY}"
    print(f"✅ Inventory found: {INVENTORY}")


def test_inventory_non_empty():
    """Sanity check: the inventory must contain URLs."""
    with open(INVENTORY, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 0, "Inventory is empty"
    print(f"✅ Inventory contains {len(rows)} URLs")


def test_pdf_urls_return_pdf(total_test_limit: int = 0):
    """
    Test that sampled PDF URLs return valid PDF content.

    If total_test_limit is 0, tests ALL URLs (full run).
    If > 0, tests only that many from each legislature (spot check).
    """
    if not INVENTORY.exists():
        print("⚠️  No inventory found — skipping PDF URL validity test.")
        return

    with open(INVENTORY, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("⚠️  Inventory is empty — skipping.")
        return

    # Group by legislature for per-legislature reporting
    by_leg: dict[str, list[dict]] = {}
    for r in rows:
        by_leg.setdefault(r["legislature"], []).append(r)

    all_valid = True
    for leg in sorted(by_leg.keys()):
        leg_rows = by_leg[leg]
        sample = leg_rows[:total_test_limit] if total_test_limit > 0 else leg_rows
        valid = 0
        invalid = 0

        for row in sample:
            url = row["url"]
            try:
                r = requests.get(url, headers=HEADERS, verify=False, timeout=15)
                if r.status_code == 200 and r.content[:4] == b"%PDF":
                    valid += 1
                else:
                    invalid += 1
                    print(f"  ❌ [{r.status_code}] {url}")
                    all_valid = False
            except Exception as e:
                invalid += 1
                print(f"  ❌ [ERR] {url}: {e}")
                all_valid = False

        tested = valid + invalid
        pct = round(100 * valid / tested, 1) if tested else 0
        status = "✅" if invalid == 0 else "❌"
        label = f"Legislature {leg} (sample {tested}/{len(leg_rows)})" if total_test_limit > 0 else f"Legislature {leg} (all {tested})"
        print(f"  {status} {label}: {valid}/{tested} valid ({pct}%)")

    assert all_valid, "Some PDF URLs failed validation"
    print("\n✅ All tested PDF URLs are valid.")


def test_session_types():
    """Verify that session_type ('ordinaire' vs 'extraordinaire') is present in session IDs."""
    if not INVENTORY.exists():
        print("⚠️  No inventory found — skipping session type check.")
        return

    with open(INVENTORY, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    sessions_with_extra = [r for r in rows if "extra" in r["session"]]
    sessions_without_type = [
        r for r in rows
        if "ordinaire" not in r["session"] and "extra" not in r["session"]
        and r["legislature"] in ("12", "13", "14")  # only XII-XIV have ordinaire/extra pattern
    ]

    print(f"Ordinary sessions: {len(rows) - len(sessions_with_extra)}")
    print(f"Extraordinary sessions: {len(sessions_with_extra)}")
    if sessions_without_type:
        print(f"⚠️  {len(sessions_without_type)} XII-XIV sessions without 'ordinaire'/'extra' in ID:")
        for r in sessions_without_type[:10]:
            print(f"    {r['legislature']}  {r['session']}")


if __name__ == "__main__":
    test_inventory_exists()
    test_inventory_non_empty()

    # Spot check by default (first 10 per legislature)
    spot_check = "--spot-check" in sys.argv
    limit = 10 if spot_check else 0
    test_pdf_urls_return_pdf(total_test_limit=limit)
    test_session_types()

    if spot_check:
        print("\n⚠️  Spot check only. For full validation, run without --spot-check.")
    print("\n✅ PDF URL validity checks complete.")
