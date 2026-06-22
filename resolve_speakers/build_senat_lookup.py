#!/usr/bin/env python3
"""
build_senat_lookup.py — Download ODSEN_HISTOGROUPES.csv from data.senat.fr
and build a cached lookup mapping (normalised_name, year) -> group_name.

The CSV has columns:
  Matricule, Id appartenance, Id fonction, Nom, Prénom,
  Code du groupe, Nom court du groupe,
  Date début appartenance, Date fin appartenance,
  Nom court fonction, Date début fonction, Date fin fonction

Output: data/reference/senateurs_lookup.json
"""
import csv
import io
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
CACHE_PATH = REFERENCE_DIR / "senateurs_lookup.json"

HISTOGROUPES_URL = "https://data.senat.fr/data/senateurs/ODSEN_HISTOGROUPES.csv"


def _normalise(name: str) -> str:
    """Normalise a senator name for lookup matching.

    Same logic as _normalise_name_key in extract_text.py.

    Year-range generation: for each senator membership record, entries are
    created for EVERY year in the tenure range (date_deb year → date_fin year).
    This ensures a debate from 2016 matches a membership that started in 2004
    and ended in 2017.

    When a senator has multiple memberships in the same year (e.g. switched
    groups mid-year), the first group encountered in the CSV is stored.
    """
    name = name.strip()
    # Normalise whitespace
    name = re.sub(r"\s+", " ", name).lower()
    # Remove accents
    for old, new in [("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
                     ("à", "a"), ("â", "a"), ("ä", "a"),
                     ("î", "i"), ("ï", "i"),
                     ("ô", "o"), ("ö", "o"),
                     ("ù", "u"), ("û", "u"), ("ü", "u"),
                     ("ç", "c"), ("œ", "oe")]:
        name = name.replace(old, new)
    return name.strip()


def fetch_senateurs():
    """Download ODSEN_HISTOGROUPES.csv and build a cached lookup."""
    print("Downloading Sénat senators dataset...")
    r = requests.get(HISTOGROUPES_URL, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from {HISTOGROUPES_URL}")

    lines = r.text.split("\n")

    # Find the real data header line (contains "Matricule" but not SQL "senmat")
    real_lines = []
    header_found = False
    for line in lines:
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        if not header_found:
            if "Matricule" in line and "senmat" not in line.lower():
                header_found = True
            continue
        real_lines.append(line)

    # Parse with csv
    reader = csv.reader(io.StringIO("\n".join(real_lines)))

    # Build lookup: (norm_name, year) -> group_name
    lookup = {}
    group_counts = defaultdict(set)  # group_name -> set of norm_names

    for row in reader:
        if len(row) < 9:
            continue
        matricule = row[0].strip()
        nom = row[3].strip()
        prenom = row[4].strip()
        groupe_code = row[5].strip()
        groupe_nom = row[6].strip()
        date_deb = row[7].strip()
        date_fin = row[8].strip()

        if not matricule or not nom:
            continue

        full_name = f"{prenom} {nom}".strip()
        norm_name = _normalise(full_name)

        # Extract year range: create an entry for every year the senator
        # held this group membership, so debates in any year match correctly.
        yr_start = int(date_deb[:4]) if (date_deb and len(date_deb) >= 4) else None
        yr_end = int(date_fin[:4]) if (date_fin and len(date_fin) >= 4) else None

        # Determine the year(s) to create entries for
        if yr_start and yr_end:
            years = range(yr_start, yr_end + 1)
        elif yr_start:
            # Ongoing membership — extend to current year
            years = range(yr_start, datetime.now().year + 1)
        elif yr_end:
            years = [yr_end]
        else:
            continue  # No date info at all

        for year in years:
            year_str = str(year)
            # Only store the first group encountered for this (name, year)
            if (norm_name, year_str) not in lookup:
                lookup[(norm_name, year_str)] = groupe_nom
                if groupe_nom:
                    group_counts[groupe_nom].add(norm_name)

    # Build surname-only index for fallback lookups
    surname_idx = {}
    for (fn, year), party in lookup.items():
        surname = fn.split()[-1] if " " in fn else fn
        if surname not in surname_idx:
            surname_idx[surname] = {}
        if year not in surname_idx[surname]:
            surname_idx[surname][year] = set()
        surname_idx[surname][year].add(party)

    # Resolve: if multiple parties for same (surname, year), store None
    surname_final = {}
    for surname, year_map in surname_idx.items():
        surname_final[surname] = {}
        for year, parties in year_map.items():
            surname_final[surname][year] = (
                list(parties)[0] if len(parties) == 1 else None
            )

    # Cache to disk (surname_final values are already resolved str|None)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    serialisable = {
        "lookup": {f"{k[0]}||{k[1]}": v for k, v in lookup.items()},
        "surname_idx": surname_final,
    }
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, ensure_ascii=False, indent=2)

    n_names = len(set(k[0] for k in lookup.keys()))
    print(f"Cached {len(lookup):,} senator->party mappings "
          f"({n_names} unique names, {len(group_counts)} groups) "
          f"to {CACHE_PATH}")

    return lookup


if __name__ == "__main__":
    # Reconfigure stdout for Windows terminals to prevent UnicodeEncodeError
    import sys
    if sys.stdout and getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    fetch_senateurs()
