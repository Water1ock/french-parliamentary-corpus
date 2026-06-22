#!/usr/bin/env python3
"""
build_leg11_lookup.py -- Scrape the Wikipedia page for the 11th legislature
(1997-2002) to build a deputy-to-party lookup.

The AMO30 dataset from data.assemblee-nationale.fr covers legislatures XII-XVII
only. For legislature XI, the authoritative structured source is the Wikipedia
page: "Liste des députés de la XIe législature de la Cinquième République"
which aggregates Journal Officiel, electoral, and parliamentary archive data.

Page structure:
  - Tables are plain <table> tags (NOT wikitable class)
  - 4 columns: Nom, (empty spacer), Groupe, Circonscription
  - pandas.read_html produces: ['Nom', 'Unnamed: 1', 'Groupe', 'Circonscription']
  - Groups: SOC, RPR, UDF, DL (or DLI), COM (or PCF), RCV, NI
  - "Apparentés" marked as "a. SOC" etc. -> we strip the "a." prefix
  - One entry per deputy (final composition as of June 18, 2002)
  - Deputies listed alphabetically by surname

Output: data/reference/deputes_leg11_lookup.json
  - Same format as deputes_lookup.json so it can be merged transparently.
"""

import json
import re
from collections import defaultdict
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
CACHE_PATH = REFERENCE_DIR / "deputes_leg11_lookup.json"

WIKI_URL = (
    "https://fr.wikipedia.org/wiki/"
    "Liste_des_d%C3%A9put%C3%A9s_de_la_XIe_l%C3%A9gislature"
    "_de_la_Cinqui%C3%A8me_R%C3%A9publique"
)

# Map Wikipedia group names to standard abbreviations used in our corpus.
# These match the AMO30 libelleAbrev values for consistency.
GROUP_MAP = {
    "SOC": "SOC",
    "PS": "SOC",
    "RPR": "RPR",
    "UDF": "UDF",
    "DL": "DL",
    "DLI": "DL",
    "COM": "COM",
    "PCF": "COM",
    "RCV": "RCV",
    "NI": "NI",
    "Non inscrit": "NI",
    "Non inscrite": "NI",
}

# The legislature key for our lookup format
LEGISLATURE = "11"


def _normalise(name: str) -> str:
    """Normalise a deputy name for lookup matching.

    Same logic as _normalise_name_key() in extract_text.py.
    """
    name = name.strip()
    # Strip "M." / "Mme" prefix (shouldn't be in Wikipedia data but be safe)
    name = re.sub(r"^(M\.|Mme)\s+", "", name, flags=re.IGNORECASE).strip()
    # Normalise whitespace, remove parenthetical notes like "[1]"
    name = re.sub(r"\s*\[.*?\]\s*", " ", name)
    name = re.sub(r"\s+", " ", name).lower()
    # Remove accents for fuzzy matching
    for old, new in [("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
                     ("à", "a"), ("â", "a"), ("ä", "a"),
                     ("î", "i"), ("ï", "i"),
                     ("ô", "o"), ("ö", "o"),
                     ("ù", "u"), ("û", "u"), ("ü", "u"),
                     ("ç", "c"), ("œ", "oe")]:
        name = name.replace(old, new)
    return name.strip()


def _parse_group(raw_group: str) -> str:
    """Parse a Wikipedia group cell into a standard abbreviation.

    Handles:
      - "SOC" -> "SOC"
      - "a. SOC" -> "SOC"  (apparenté)
      - "Non inscrit" -> "NI"
      - Unknown -> raw value (logged as warning)
    """
    g = raw_group.strip()
    # Strip "a." prefix for apparentés
    g = re.sub(r"^a\.\s*", "", g, flags=re.IGNORECASE).strip()
    if not g:
        return ""
    mapped = GROUP_MAP.get(g, "")
    if not mapped:
        # Try case-insensitive match
        g_upper = g.upper()
        mapped = GROUP_MAP.get(g_upper, "")
    if not mapped:
        print(f"  WARNING: Unknown group '{raw_group}' -> storing as '{g}'")
        return g
    return mapped


def fetch_leg11() -> dict:
    """Scrape Wikipedia and build the Leg 11 lookup.

    Returns: dict with keys 'lookup' and 'surname_idx', same structure
             as load_deputes() output, so it can be merged transparently.
    """
    print(f"Fetching Wikipedia page: {WIKI_URL}")
    r = requests.get(WIKI_URL, timeout=30, headers={
        "User-Agent": "FrenchParliamentaryCorpus/1.0 (research project; "
                      "contact via GitHub)"
    })
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from Wikipedia")

    # pandas.read_html() finds all <table> elements on the page
    tables = pd.read_html(StringIO(r.text))
    print(f"  Found {len(tables)} tables on page")

    # Filter: deputy tables have 4 columns (Nom, spacer, Groupe, Circonscription)
    # and contain 'Nom' in column 0 header and 'Groupe' in column 2 header.
    deputy_tables = []
    for t in tables:
        if t.shape[1] != 4:
            continue
        cols = [str(c).strip() for c in t.columns]
        if "Nom" in cols[0] and "Groupe" in cols[2] and t.shape[0] > 2:
            deputy_tables.append(t)
    print(f"  Found {len(deputy_tables)} deputy tables (4-col, Nom+Groupe headers)")

    # Build lookup
    lookup = {}  # (norm_name, leg) -> party
    seen_names = set()
    skipped = 0

    for t in deputy_tables:
        # Column 0 = Nom, Column 2 = Groupe (column 1 is an empty spacer)
        for idx in range(len(t)):
            raw_name = str(t.iloc[idx, 0]).strip()
            raw_group = str(t.iloc[idx, 2]).strip()

            # Skip header rows: if col 0 is "Nom", it's a header row
            if raw_name in ("Nom", "nan", ""):
                continue
            # Skip section markers or TOC entries
            if raw_name.startswith("Sommaire"):
                continue
            # Skip if name starts with "[" (reference markers)
            if raw_name.startswith("[") and raw_name.endswith("]"):
                continue

            # Parse group
            party = _parse_group(raw_group)
            if not party:
                skipped += 1
                continue

            # Normalise name
            norm_name = _normalise(raw_name)
            if not norm_name:
                skipped += 1
                continue

            # Store: first-wins for duplicates (same as AMO30/Sénat pattern)
            key = (norm_name, LEGISLATURE)
            if key not in lookup:
                lookup[key] = party
                seen_names.add(norm_name)

    print(f"  Parsed {len(lookup)} deputy entries ({len(seen_names)} unique names)")
    if skipped:
        print(f"  Skipped {skipped} rows (empty name/group)")

    # Build surname index (same structure as load_deputes() produces)
    surname_map = defaultdict(list)
    for (fn, leg), party in lookup.items():
        surname = fn.split()[-1] if " " in fn else fn
        surname_map[surname].append((leg, party))

    surname_idx = {}
    for surname, entries in surname_map.items():
        leg_parties = defaultdict(set)
        for leg, party in entries:
            leg_parties[leg].add(party)
        surname_idx[surname] = {
            leg: (list(parties)[0] if len(parties) == 1 else None)
            for leg, parties in leg_parties.items()
        }

    # Cache to disk
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    result = {
        "lookup": {f"{k[0]}||{k[1]}": v for k, v in lookup.items()},
        "surname_idx": surname_idx,
        "_meta": {
            "source": WIKI_URL,
            "description": (
                "Deputy-to-party lookup for the 11th legislature (1997-2002), "
                "sourced from Wikipedia's authoritative list of deputies. "
                "The AMO30 structured dataset from data.assemblee-nationale.fr "
                "covers legislatures XII-XVII only."
            ),
            "legislature": "11",
            "total_entries": len(lookup),
            "unique_names": len(seen_names),
            "groups": sorted(set(v for _, v in lookup.items())),
        },
    }

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Print group distribution
    from collections import Counter
    group_counts = Counter(v for _, v in lookup.items())
    print(f"\n  Group distribution:")
    for group, count in group_counts.most_common():
        print(f"    {group}: {count}")

    print(f"\n  Cached to {CACHE_PATH}")
    return result


if __name__ == "__main__":
    # Reconfigure stdout for Windows terminals
    import sys
    if sys.stdout and getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    fetch_leg11()
