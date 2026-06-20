#!/usr/bin/env python3
"""
build_senat_url_inventory.py - Discover every Senat plenary debate URL.

This script builds a flat CSV inventory of Senat debate URLs covering
January 2003 through December 31, 2025, by parsing the Senat official
open-data PostgreSQL dump at data.senat.fr.

Unlike the Assemblee nationale (which requires scraping three different
URL patterns), the Senat provides a single authoritative source: the
debats table in the data.senat.fr PostgreSQL dump.

DATA SOURCE
    https://data.senat.fr/data/debats/debats.zip
    Contains: debats.sql (314 MB uncompressed PostgreSQL dump)
    Table: debats (2,816 rows, 2003-present)
    Columns: datsea (session date), debsyn (sync status), autinc,
             deburl (relative path to debate report), numero (session
             number), estcongres (Congres flag), libspec, etavidcod, cpterr

ERA SPLIT

    2003-2007 (HTML era):
        The deburl points to HTML debate pages. These contain the full
        debate text but are NOT downloadable PDFs. Example session page:
          https://www.senat.fr/seances/s200301/s20030115/st20030115000.html
        These session page URLs are stored in the inventory. HTML
        extraction is handled separately from PDF download.

    2008-2025 (PDF era):
        The deburl points to a session page that links to a PDF. The PDF
        URL is reliably derived by replacing the session page path:
          Session page: s{YYYYMM}/s{YYYYMMDD}/st{YYYYMMDD}xxx.html
          PDF:          s{YYYYMM}/s{YYYYMMDD}/s{YYYYMMDD}.pdf
        Validated across 8 dates (2008-2025), all return %%PDF content.

    Congres (joint sessions):
        Excluded from this inventory (1 session, 2009). This matches the
        AN approach where Congres is deferred.

COVERAGE GAP: 2000-2002
    The Senat digital archive began January 2003. Pre-2003 monthly
    indexes return 403 Forbidden. The 2000-2002 debates exist only as
    printed Journal Officiel, digitized via Gallica (BNF) - not directly
    accessible on senat.fr. This 3-year gap is an institutional
    limitation of the Senat digital infrastructure.

OUTPUT
    data/senat_inventory.csv
    Columns: legislature, session, url, date

USAGE
    python inventory/build_senat_url_inventory.py
"""

import csv
import io
import zipfile
from pathlib import Path

import requests

requests.packages.urllib3.disable_warnings()

DEBATS_URL = "https://data.senat.fr/data/debats/debats.zip"
BASE_SENAT = "https://www.senat.fr"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FrenchParliamentaryCorpus/1.0)"}

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = OUTPUT_DIR / "senat_inventory.csv"
DEBATS_CACHE = OUTPUT_DIR / "debats.zip"

# Scope cutoff: include sessions through December 31, 2025 (inclusive).
# Sessions from 2026 onward are excluded.
CUTOFF_DATE = "2025-12-31"

# The Senat PDF era begins in 2008. Before this, debates are HTML only.
PDF_ERA_START = "2008-01-01"

# PostgreSQL COPY format uses backslash-N for NULL values.
# We compare against this literal two-character string.
PG_NULL = chr(92) + "N"  # backslash + N, avoids Python unicode escape


# ----------------------------------------------------------------------
# DOWNLOAD AND PARSE
# ----------------------------------------------------------------------

def _download_debats_sql():
    # type: () -> str
    """Download debats.zip from data.senat.fr (with caching) and return
    the debats.sql contents as a string."""
    if DEBATS_CACHE.exists():
        size = DEBATS_CACHE.stat().st_size
        print(f"Using cached {DEBATS_CACHE} ({size:,} bytes)")
        zip_data = DEBATS_CACHE.read_bytes()
        try:
            zipfile.ZipFile(io.BytesIO(zip_data))
        except (zipfile.BadZipFile, Exception):
            print("  Cached zip corrupted, re-downloading...")
            DEBATS_CACHE.unlink()
            return _download_debats_sql()
    else:
        print(f"Downloading {DEBATS_URL} ...")
        try:
            r = requests.get(DEBATS_URL, headers=HEADERS, verify=False, timeout=300)
            r.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to download {DEBATS_URL}: {e}") from e
        zip_data = r.content
        DEBATS_CACHE.write_bytes(zip_data)
        print(f"  Downloaded {len(zip_data):,} bytes, cached to {DEBATS_CACHE}")

    zipf = zipfile.ZipFile(io.BytesIO(zip_data))
    if "debats.sql" not in zipf.namelist():
        raise FileNotFoundError("debats.sql not found in debats.zip")

    content = zipf.read("debats.sql").decode("latin-1", errors="replace")
    print(f"  Extracted debats.sql ({len(content):,} chars)")
    return content


def _parse_debats_copy_data(content):
    # type: (str) -> list[dict]
    """Parse the COPY-format data for the debats table.

    PostgreSQL COPY format (tab-separated, backslash-N for NULL,
    backslash-dot terminator).

    Returns list of dicts with keys: datsea, debsyn, autinc, deburl,
    numero, estcongres, libspec, etavidcod, cpterr.
    """
    # Find the COPY debats section
    idx_start = content.find("COPY debats")
    if idx_start < 0:
        raise ValueError("COPY debats statement not found in SQL dump")

    # Find start of data (line after "FROM stdin;")
    idx_data = content.find("\n", idx_start) + 1

    # Find end of data (the backslash-dot terminator on its own line)
    terminator = "\n" + chr(92) + "." + "\n"
    idx_end = content.find(terminator, idx_data)
    if idx_end < 0:
        # Fallback: find backslash-dot anywhere
        idx_dot = content.find(chr(92) + ".", idx_data)
        if idx_dot < 0:
            raise ValueError("COPY data terminator not found")
        idx_end = idx_dot - 1

    data_str = content[idx_data:idx_end]
    lines = [l for l in data_str.split("\n") if l.strip()]
    print(f"  Parsed {len(lines):,} COPY data rows")

    sessions = []  # type: list[dict]
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        sessions.append({
            "datsea": parts[0].strip(),
            "debsyn": parts[1].strip(),
            "autinc": parts[2].strip(),
            "deburl": None if parts[3] == PG_NULL else parts[3].strip(),
            "numero": None if parts[4] == PG_NULL else parts[4].strip(),
            "estcongres": parts[5].strip(),
            "libspec": None if parts[6] == PG_NULL else parts[6].strip(),
            "etavidcod": parts[7].strip(),
            "cpterr": parts[8].strip(),
        })
    return sessions


# ----------------------------------------------------------------------
# URL DERIVATION
# ----------------------------------------------------------------------

def _derive_pdf_url(deburl):
    # type: (str) -> str
    """Derive the PDF URL from a Senat session page relative path.

    Session page: s200801/s20080131/st20080131000.html
    PDF:          s200801/s20080131/s20080131.pdf

    The session page filename uses 'st' prefix + date + sequence number.
    The PDF filename uses 's' prefix + date (no sequence number).
    """
    parts = deburl.split("/")
    if len(parts) != 3:
        # Unexpected format - log warning and return session page URL
        print(f"  WARN Unexpected deburl format (expected 3 parts): {deburl}")
        return f"{BASE_SENAT}/seances/{deburl}"

    month_dir = parts[0]  # s200801
    day_dir = parts[1]    # s20080131
    pdf_path = f"{month_dir}/{day_dir}/{day_dir}.pdf"
    return f"{BASE_SENAT}/seances/{pdf_path}"


def _session_page_url(deburl):
    # type: (str) -> str
    """Convert a relative deburl path to a full session page URL."""
    return f"{BASE_SENAT}/seances/{deburl}"


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def build_inventory():
    # type: () -> None
    """Parse debats.sql and write the Senat URL inventory CSV."""
    print("=== Senat URL Inventory ===\n")

    # 1. Download and parse
    try:
        sql_content = _download_debats_sql()
        all_sessions = _parse_debats_copy_data(sql_content)
    except Exception as e:
        print(f"ERR Failed to load Senat data: {e}")
        return
    print(f"  Total sessions in database: {len(all_sessions):,}")

    # 2. Filter and derive URLs
    rows = []  # type: list[dict]
    skipped_congres = 0
    skipped_after_cutoff = 0
    skipped_before_2003 = 0
    skipped_no_url = 0

    for s in all_sessions:
        date_str = s["datsea"][:10]  # "2003-01-14 00:00:00" -> "2003-01-14"

        # Exclude sessions before 2003 (one 2001 outlier in the database)
        if date_str < "2003-01-01":
            skipped_before_2003 += 1
            continue

        # Exclude sessions after the cutoff date
        if date_str > CUTOFF_DATE:
            skipped_after_cutoff += 1
            continue

        # Exclude Congres (joint AN+Senat sessions)
        if s["estcongres"] == "O":
            skipped_congres += 1
            continue

        # Exclude sessions without a deburl
        if not s["deburl"]:
            skipped_no_url += 1
            continue

        # Choose URL based on era:
        #   2003-2007: HTML session page URL (deburl is the debate page itself)
        #   2008+:     PDF URL (derived from deburl session page path)
        if date_str >= PDF_ERA_START:
            url = _derive_pdf_url(s["deburl"])
        else:
            url = _session_page_url(s["deburl"])

        rows.append({
            "legislature": "S",
            "session": date_str,
            "url": url,
            "date": date_str,
        })

    # 3. Write CSV
    fieldnames = ["legislature", "session", "url", "date"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # 4. Report
    print(f"\n  Included: {len(rows):,} sessions (2003-01-01 to {CUTOFF_DATE})")
    print("  Excluded:")
    print(f"    Before 2003:      {skipped_before_2003:>5}")
    print(f"    After cutoff:     {skipped_after_cutoff:>5}")
    print(f"    Congres:          {skipped_congres:>5}")
    print(f"    Missing deburl:   {skipped_no_url:>5}")

    # Era breakdown
    html_era = sum(1 for r in rows if r["date"] < PDF_ERA_START)
    pdf_era = sum(1 for r in rows if r["date"] >= PDF_ERA_START)
    print("\n  Era breakdown:")
    print(f"    2003-2007 (HTML): {html_era:>5} sessions")
    print(f"    2008-2025 (PDF):  {pdf_era:>5} sessions")

    print(f"\nDone. {len(rows)} URLs written to {OUTPUT_CSV}")


if __name__ == "__main__":
    build_inventory()
