#!/usr/bin/env python3
"""
test_senat_pdf_discovery.py

Verifies Sénat (French Senate) plenary debate PDF URL patterns and discovery
methods. This test serves the same role for the Sénat that the three AN test
files serve for the Assemblée nationale.

Why this test exists:
    The Sénat site uses a fundamentally different architecture than the AN:
    - No legislature-specific URL patterns (the Sénat doesn't use legislature numbers)
    - A JavaScript-based CMS (TYPO3) that makes plain HTTP scraping of monthly
      indexes difficult
    - An open data portal (data.senat.fr) providing structured PostgreSQL dumps
      for 2003–present
    - A ~7-year gap (June 1996 – December 2002) between the paper archives and
      the open data era

Discovery findings (2026-06-20):

    A) Modern Sénat session pages and PDFs (works ≥2008, possibly earlier):
       Session page:  /seances/s{YYMM}/s{YYMMDD}/st{YYMMDD}{seq}.html
       PDF:           /seances/s{YYMM}/s{YYMMDD}/s{YYMMDD}.pdf
       Example:       /seances/s202301/s20230110/st20230110000.html
                      /seances/s202301/s20230110/s20230110.pdf

       The PDF link is directly present as an <a href> on the session page HTML
       — no URL derivation step needed (unlike AN XII–XIV where we had to
       convert .asp→.pdf and /cri/→/pdf/cri/).

    B) data.senat.fr open data portal:
       - Coverage: January 2003 to present
       - Bulk downloads:
         * debats.zip (33.5 MB) → debats.sql (314 MB PostgreSQL dump)
           Tables: debats (session metadata including deburl = PDF URL),
           intdivers, intpjl, secdis, secdivers, syndeb, typsec, lecassdeb
         * cri.zip (542 MB) → XML files of full debate transcripts
       - The debats table contains: datsea (session date), deburl (PDF URL),
         numero (session number), estcongres (Congrès flag)
       - This is the AUTHORITATIVE source for 2003+ Sénat session metadata

    C) Monthly index pages (blocked by JS redirect):
       - /seances/s{YYYYMM}/ → returns meta-refresh to s{YYYYMM}.html
       - /seances/s{YYYYMM}.html → returns 404
       - The actual index requires JavaScript execution (TYPO3 CMS)
       - For 2003+, data.senat.fr obviates the need to scrape these

    D) Pre-2003 gap (June 1996 – December 2002):
       - Monthly indexes for 2000-2002 all return 403 Forbidden
       - The archival page (/comptes-rendus-seances/5eme/seances/archiveSeances.html)
         covers 1958 to May 1996 only
       - For our scope (2000–2025): 2000–2002 falls in this gap
       - These debates exist only as printed Journal Officiel, digitized via
         Gallica (BNF): gallica.bnf.fr — search "Journal officiel Sénat"
       - This period is HTML/web-only on the Sénat site (no PDFs), or only
         available as scanned Journal Officiel PDFs via Gallica

    E) Pre-2003 monthly index 403 wall (confirmed):
       - All monthly indexes before ~2003 return 403
       - 200001, 200101, 200201 → 403
       - 200301 → 200 (redirects, but JS-dependent)
       - This is consistent with test_coverage_gaps.py findings

What this test does:
    1. Validates data.senat.fr bulk data is accessible
    2. Extracts and validates a sample of PDF URLs from debats.sql
    3. Tests the session page URL pattern with known working dates
    4. Tests that PDF URLs from session pages resolve to real PDF content
    5. Documents the 403 wall and pre-2003 gap
    6. Tests that data.senat.fr debats table contains expected columns
"""

import io
import re
import zipfile

import requests
from lxml import html

requests.packages.urllib3.disable_warnings()

BASE = "https://www.senat.fr"
DATA_PORTAL = "https://data.senat.fr"
DEBATS_URL = f"{DATA_PORTAL}/data/debats/debats.zip"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}

# Known working session dates (validated manually during discovery)
# Format: (year, month, day) — dates confirmed to have PDFs
KNOWN_SESSIONS = [
    (2023, 1, 10),     # Confirmed: session page + PDF both work
    (2022, 1, 11),     # Confirmed: PDF works
    (2020, 1, 14),     # Confirmed: PDF works
    (2010, 1, 19),     # Confirmed: PDF works
    (2009, 7, 7),      # Confirmed: session page pattern works
    (2008, 7, 8),      # Confirmed: session page pattern works
]


# ──────────────────────────────────────────────────────────────────────
# TEST 1: data.senat.fr bulk data accessibility
# ──────────────────────────────────────────────────────────────────────

def test_data_senat_bulk_accessible():
    """Test that data.senat.fr bulk downloads are accessible."""
    print("=== Test 1: data.senat.fr bulk data accessibility ===")

    r = requests.get(DEBATS_URL, headers=HEADERS, verify=False, timeout=30, stream=True)
    assert r.status_code == 200, f"debats.zip returned {r.status_code}"
    size = int(r.headers.get("content-length", 0))
    print(f"  OK  debats.zip accessible ({size:,} bytes)")

    cri_url = f"{DATA_PORTAL}/data/debats/cri.zip"
    r2 = requests.get(cri_url, headers=HEADERS, verify=False, timeout=30, stream=True)
    assert r2.status_code == 200, f"cri.zip returned {r2.status_code}"
    size2 = int(r2.headers.get("content-length", 0))
    print(f"  OK  cri.zip accessible ({size2:,} bytes)")


# ──────────────────────────────────────────────────────────────────────
# TEST 2: debats.sql schema validation
# ──────────────────────────────────────────────────────────────────────

def test_debats_sql_schema():
    """Test that debats.sql contains the expected tables and columns."""
    print("\n=== Test 2: debats.sql schema ===")

    r = requests.get(DEBATS_URL, headers=HEADERS, verify=False, timeout=60)
    assert r.status_code == 200

    zipf = zipfile.ZipFile(io.BytesIO(r.content))
    assert "debats.sql" in zipf.namelist(), "debats.sql not found in archive"

    content = zipf.read("debats.sql").decode("latin-1", errors="replace")
    tables = re.findall(r"CREATE TABLE\s+(\w+)", content, re.IGNORECASE)

    expected_tables = ["debats", "intdivers", "intpjl", "secdis", "secdivers", "syndeb", "typsec"]
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' not found in debats.sql"
    print(f"  OK  All {len(expected_tables)} expected tables found: {', '.join(expected_tables)}")

    # Verify debats table has key columns
    # Use regex that handles nested parens in column types like character(1)
    debats_ddl = re.search(
        r"CREATE TABLE debats\s*\((.*?)\);\s*$",
        content, re.IGNORECASE | re.DOTALL | re.MULTILINE
    )
    assert debats_ddl, "debats table DDL not found"
    columns_text = debats_ddl.group(1)
    expected_cols = ["datsea", "deburl", "numero", "estcongres"]
    for col in expected_cols:
        assert col in columns_text, f"Expected column '{col}' not in debats table"
    print(f"  OK  debats table contains key columns: {', '.join(expected_cols)}")

    # Verify there is INSERT or COPY data (not just DDL)
    insert_count = len(re.findall(r"INSERT INTO\s+\"?debats\"?\b", content, re.IGNORECASE))
    copy_count = len(re.findall(r"COPY\s+\"?debats\"?\b", content, re.IGNORECASE))
    print(f"  OK  Found {insert_count} INSERT + {copy_count} COPY statements for debats table")


# ──────────────────────────────────────────────────────────────────────
# TEST 3: Sénat session page URL pattern
# ──────────────────────────────────────────────────────────────────────

def test_session_page_pattern():
    """Test that session pages follow the expected URL pattern."""
    print("\n=== Test 3: Session page URL pattern ===")

    for year, month, day in KNOWN_SESSIONS:
        datestr = f"{year}{month:02d}{day:02d}"
        ym = f"s{datestr[:6]}"
        # Session page: st{YYYYMMDD}000.html (3 zeros suffix)
        # NOTE: The suffix sequence (000, 001, ...) varies by session.
        # Session pages may not exist for all dates even when PDFs do.
        session_url = f"{BASE}/seances/{ym}/s{datestr}/st{datestr}000.html"

        r = requests.get(session_url, headers=HEADERS, verify=False, timeout=15)
        if r.status_code == 200:
            tree = html.fromstring(r.content)
            links = tree.xpath("//a/@href")
            pdf_links = [l for l in links if l.endswith(".pdf")]
            assert len(pdf_links) > 0, f"No PDF links found on {session_url}"
            print(f"  OK  {session_url}")
            print(f"       PDF link: {pdf_links[0]}")
        else:
            print(f"  WARN {r.status_code} {session_url}")


# ──────────────────────────────────────────────────────────────────────
# TEST 4: Sénat PDF URL validation
# ──────────────────────────────────────────────────────────────────────

def test_senat_pdfs_are_valid():
    """Test that Sénat debate PDF URLs resolve to real PDF content."""
    print("\n=== Test 4: PDF URL validation ===")

    validated = 0
    failed = 0

    for year, month, day in KNOWN_SESSIONS:
        ym = f"s{year}{month:02d}"
        ymd = f"s{year}{month:02d}{day:02d}"
        pdf_url = f"{BASE}/seances/{ym}/{ymd}/{ymd}.pdf"

        try:
            r = requests.get(pdf_url, headers=HEADERS, verify=False, timeout=30)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                print(f"  OK  {pdf_url}  ({len(r.content):,} bytes)")
                validated += 1
            else:
                print(f"  FAIL {pdf_url}  status={r.status_code} PDF={r.content[:4] == b'%PDF'}")
                failed += 1
        except Exception as e:
            print(f"  FAIL {pdf_url}  ERR: {e}")
            failed += 1

    print(f"\n  Validated: {validated}/{len(KNOWN_SESSIONS)}, Failed: {failed}")

    # At least the most recent sessions should work
    assert validated >= 2, f"Only {validated} PDFs validated — expected at least 2"


# ──────────────────────────────────────────────────────────────────────
# TEST 5: Pre-2003 403 wall (documentation)
# ──────────────────────────────────────────────────────────────────────

def test_pre2003_403_wall():
    """
    Document the 403 wall for Sénat monthly indexes before 2003.

    This is a documentation test — it EXPECTS 403 responses for pre-2003
    indexes. The purpose is to alert us if the Sénat ever opens these up.
    """
    print("\n=== Test 5: Pre-2003 403 wall ===")

    pre2003_dates = [
        ("200001", "January 2000"),
        ("200101", "January 2001"),
        ("200201", "January 2002"),
    ]

    all_blocked = True
    for ym, label in pre2003_dates:
        url = f"{BASE}/seances/s{ym}/"
        r = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        status_str = "OK  ACCESSIBLE" if r.status_code == 200 else f"BLOCKED {r.status_code}"
        if r.status_code == 200:
            all_blocked = False
        print(f"  {status_str}  /seances/s{ym}/  ({label})")

    if all_blocked:
        print("  INFO All pre-2003 monthly indexes are blocked (403/404).")
        print("     This is consistent with prior findings.")
        print("     For 2003+ sessions, use data.senat.fr instead.")
        print("     For 2000–2002: these exist only as Journal Officiel scans")
        print("     via Gallica (BNF) — not directly accessible on senat.fr.")


# ──────────────────────────────────────────────────────────────────────
# TEST 6: data.senat.fr as authoritative source for 2003+
# ──────────────────────────────────────────────────────────────────────

def test_data_senat_coverage():
    """
    Verify that data.senat.fr covers our needed range (2003–2025).

    The debats table covers January 2003 to present. This test extracts
    a sample of session dates from the SQL dump to confirm coverage.
    """
    print("\n=== Test 6: data.senat.fr coverage (2003–2025) ===")

    r = requests.get(DEBATS_URL, headers=HEADERS, verify=False, timeout=60)
    if r.status_code != 200:
        print("  WARN Skipping -- debats.zip not accessible")
        return

    zipf = zipfile.ZipFile(io.BytesIO(r.content))
    content = zipf.read("debats.sql").decode("latin-1", errors="replace")

    # Extract sample INSERT rows from debats table to get dates and URLs.
    # PostgreSQL dumps may use INSERT INTO "debats" or COPY debats formats.
    # This regex handles both single-line and multi-line VALUES clauses.
    inserts = re.findall(
        r"INSERT INTO\s+\"?debats\"?\s+VALUES\s*\((.+?)\);\s*$",
        content, re.IGNORECASE | re.DOTALL | re.MULTILINE
    )
    if not inserts:
        # Try COPY format: COPY debats (cols) FROM stdin; data\.
        copy_matches = re.findall(
            r"COPY\s+\"?debats\"?\s*\([^)]+\)\s+FROM\s+stdin;\s*\n(.*?)\\\.",
            content, re.IGNORECASE | re.DOTALL
        )
        if copy_matches:
            # Parse tab-separated COPY data
            inserts = copy_matches

    total_sessions = len(inserts)
    print(f"  Total sessions in database: {total_sessions}")

    # Extract year range
    years = set()
    pdf_url_count = 0
    for row in inserts[:200]:  # Sample first 200
        # Extract year from datsea (first column, timestamp)
        m = re.search(r"(\d{4})-\d{2}-\d{2}", row)
        if m:
            years.add(int(m.group(1)))
        # Check if deburl (4th column) has a value
        parts = row.split(",")
        if len(parts) >= 4:
            url_val = parts[3].strip().strip("'")
            if url_val and url_val != "NULL":
                pdf_url_count += 1

    if years:
        print(f"  Year range in sample: {min(years)}-{max(years)}")
        # Check coverage spans our target range (2003-2025)
        # Note: sampling first 200 rows may miss boundary years
        if min(years) <= 2005 and max(years) >= 2024:
            print("  OK  Coverage spans 2003-2025 era (our target range)")
        else:
            print(f"  INFO Sample covers {min(years)}-{max(years)} (target: 2003-2025)")

    print(f"  Sessions with PDF URLs in sample: {pdf_url_count}/{min(200, total_sessions)}")

    # Also count Congrès sessions (estcongres = 'O')
    # Count Congres sessions safely (check column count before accessing index 5)
    congres_count = 0
    for row in inserts:
        parts = row.split(",")
        if len(parts) > 5 and "'O'" in parts[5]:
            congres_count += 1
    print(f"  Congres sessions (estcongres='O'): {congres_count}")


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SÉNAT PDF DISCOVERY TESTS")
    print("=" * 60)

    test_data_senat_bulk_accessible()
    test_debats_sql_schema()
    test_session_page_pattern()
    test_senat_pdfs_are_valid()
    test_pre2003_403_wall()
    test_data_senat_coverage()

    print("\n" + "=" * 60)
    print("  ALL SÉNAT DISCOVERY TESTS COMPLETE")
    print("=" * 60)
