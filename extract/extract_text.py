#!/usr/bin/env python3
"""
extract_text.py -- Extract structured text from debate PDFs.

Output schema (Option A + B):
  speaker_name, speaker_party, speech, debate_title,
  date, legislature, chamber, session_type, speaker_role

Usage:
  python extract/extract_text.py                   # Full-corpus extraction
  python extract/extract_text.py --test            # 7-PDF test batch
  python extract/extract_text.py --fetch-deputes   # Download deputes dataset only

Design:
  - Incremental CSV: each PDF's rows are appended immediately to output file
  - Extraction log: per-file success/failure tracking
  - Checkpoint-resume: skips PDFs already in the output log
  - Deputes lookup: downloaded once, cached locally
"""

import csv
import io
import json
import os
import re
import sys
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pdfplumber
import requests

# ------ Paths ----------------------------------------------------------------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = PROJECT_ROOT / "data" / "pdfs"
AN_INVENTORY = PROJECT_ROOT / "data" / "pdf_inventory.csv"
SENAT_INVENTORY = PROJECT_ROOT / "data" / "senat_inventory.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "extracted"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
SPEECHES_PATH = OUTPUT_DIR / "speeches.csv"
EXTRACTION_LOG = OUTPUT_DIR / "extraction_log.csv"
DEPUTES_CACHE = REFERENCE_DIR / "deputes_lookup.json"
DEPUTES_LEG11_CACHE = REFERENCE_DIR / "deputes_leg11_lookup.json"
SENATEURS_CACHE = REFERENCE_DIR / "senateurs_lookup.json"

DEPUTES_URL = (
    "http://data.assemblee-nationale.fr/static/openData/repository/17/amo/"
    "tous_acteurs_mandats_organes_xi_legislature/"
    "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip"
)

# ------ Constants ------------------------------------------------------------------------------------------------------------------------

Y_TOLERANCE = 4  # pts -- words within this vertical range are on the same line

HEADER_RE = re.compile(
    r"(?:\d+\s+)?"
    r"(ASSEMBL[ÉE]E\s*NATIONALE|S[ÉE]NAT)"
    r".*"
    r"[Ss][ÉE]ANCE\s+DU\s+\d{1,2}\s+\w+\s+\d{4}"
    r"(?:\s+\d+)?$",
    re.IGNORECASE,
)

# Speaker-introduction: "M. le président. La parole est à M. X."
PRESIDENT_INTRO_RE = re.compile(
    r"^(M\.|Mme)\s+le\s+pr[ée]sidente?\."
    r"\s+La\s+parole\s+est\s+[àa]\s+"
    r"((?:M\.|Mme)\s+\S+(?:\s+\S+)*)",
    re.IGNORECASE,
)

# Speaker turn: "M. Name." or "Mme Name." at start of line
SPEAKER_TURN_RE = re.compile(
    r"^(M\.|Mme)\s+"
    r"((?:[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŸ][a-zàâäéèêëîïôöùûüçÿœæ]+|d[eu]|d'|l'|la)\s?)+"
    r"\.",
    re.IGNORECASE,
)

NAME_ROLE_SPLIT_RE = re.compile(r"^([^,]+),\s*(.+)$")

# Page-header lines that contain session date but not the actual debate topic.
# Matches patterns like:
#   "SÉANCE DU 9 DÉCEMBRE 1997"
#   "SÉANCE DU 13 OCTOBRE 1999 7237"
#   "48 ASSEMBLÉE NATIONALE – 2e"
#   "ASSEMBLÉE NATIONALE – 1re"
#   "4 ASSEMBLÉE NATIONALE –"
#   "4246 SÉNAT – SÉANCE"
#   "4244 SÉNAT – SÉANCE DU 17 MARS 2016"
#   "DU 17 MARS 2016"
PAGE_HEADER_RE = re.compile(
    r"^(?:\d+\s+)?"
    r"(?:"
    r"S[ÉE]ANCE\s+DU\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}"
    r"|"
    r"(?:ASSEMBL[ÉE]E\s*NATIONALE|S[ÉE]NAT)\s+[\u2010-\u2015\u2212\uF6BB\-–]"
    r"(?:\s*\d+(?:re?|e|ème))?"
    r"(?:\s*S[ÉE]ANCE(?:\s+DU(?:\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4})?)?)?"
    r"|"
    r"DU\s+\d{1,2}\s+[A-ZÀ-ÿ]+\s+\d{4}"
    r")"
    r"(?:\s+\d+)?$",
    re.IGNORECASE,
)

MONTH_MAP = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "decembre": 12,
}
MONTHS_PATTERN = "|".join(MONTH_MAP.keys())


# ------ Data structures --------------------------------------------------------------------------------------------------------

@dataclass
class SpeechRecord:
    """One speaker turn with the final Option A + B schema."""
    speaker_name: str = ""
    speaker_party: str = ""
    speech: str = ""
    debate_title: str = ""
    date: str = ""
    legislature: str = ""
    chamber: str = ""
    session_type: str = ""
    speaker_role: str = ""
    page: int = 0  # internal, dropped in CSV output


SPEECH_FIELDS = [
    "speaker_name", "speaker_party", "speech", "debate_title",
    "date", "legislature", "chamber", "session_type", "speaker_role",
]


# ------ Deputes lookup (Option B) ------------------------------------------------------------------------------------

def fetch_deputes():
    """Download the deputes historical JSON zip and build a cached lookup.

    The lookup maps (normalised_name, legislature) -> party_abbreviation.

    Returns: dict { (name_key, leg_str): party_abbrev }
    """
    print("Downloading deputes dataset...")
    r = requests.get(DEPUTES_URL, timeout=120)
    z = zipfile.ZipFile(io.BytesIO(r.content))

    # First pass: build organe lookup for political groups
    organes = {}
    for fname in z.namelist():
        if not fname.startswith("json/organe/"):
            continue
        try:
            data = json.loads(z.read(fname).decode("utf-8"))
            org = data.get("organe", {})
            oid = org.get("uid", "")
            code_type = org.get("codeType", "")
            if code_type == "GP":  # Groupe politique
                libelle = org.get("libelleAbrev", "") or org.get("libelle", "")
                organes[oid] = libelle
        except Exception:
            continue

    # Second pass: build actor -> party lookup per legislature
    lookup = {}  # (norm_name, leg) -> party
    for fname in z.namelist():
        if not fname.startswith("json/acteur/"):
            continue
        try:
            data = json.loads(z.read(fname).decode("utf-8"))
            acteur = data.get("acteur", {})
            ident = acteur.get("etatCivil", {}).get("ident", {})
            nom = (ident.get("nom", "") or "").strip().upper()
            prenom = (ident.get("prenom", "") or "").strip()
            if not nom:
                continue
            nom_key = _normalise_name_key(f"{prenom} {nom}")

            mandats = acteur.get("mandats", {}).get("mandat", [])
            if not isinstance(mandats, list):
                mandats = [mandats]

            for m in mandats:
                leg = str(m.get("legislature", ""))
                type_org = m.get("typeOrgane", "")
                if not leg.isdigit():
                    continue
                # Find party from GP (groupe politique) mandates
                if type_org != "GP":
                    continue
                org_ref = m.get("organes", {}).get("organeRef", [])
                if isinstance(org_ref, dict):
                    org_ref = org_ref.get("#text", "")
                if isinstance(org_ref, list):
                    org_ref = org_ref[0] if org_ref else ""
                    if isinstance(org_ref, dict):
                        org_ref = org_ref.get("#text", "")
                party = organes.get(str(org_ref), "")
                lookup[(nom_key, leg)] = party
        except Exception:
            continue

    # Cache to disk
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    serialisable = {f"{k[0]}||{k[1]}": v for k, v in lookup.items()}
    with open(DEPUTES_CACHE, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, ensure_ascii=False, indent=2)
    print(f"Cached {len(lookup):,} depute lookups to {DEPUTES_CACHE}")
    z.close()
    return lookup


def load_deputes() -> dict:
    """Load cached deputes lookup, or download if missing.

    Returns a dict with keys:
      - "lookup": {(norm_name, leg): party}  (full-name lookup)
      - "surname_idx": {surname: {leg: party_or_None}}
        (surname-only index; None means ambiguous)
    """
    if DEPUTES_CACHE.exists():
        with open(DEPUTES_CACHE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        lookup = {tuple(k.split("||")): v for k, v in raw.items()}
    else:
        lookup = fetch_deputes()

    # Build surname reverse index for O(1) lookups
    # Merge Leg 11 Wikipedia-sourced lookup if available
    if DEPUTES_LEG11_CACHE.exists():
        with open(DEPUTES_LEG11_CACHE, "r", encoding="utf-8") as f:
            leg11_raw = json.load(f)
        leg11_lookup = {tuple(k.split("||")): v
                        for k, v in leg11_raw.get("lookup", {}).items()}
        # Merge: only add Leg 11 entries if no AMO30 entry exists for that key
        for k, v in leg11_lookup.items():
            if k not in lookup:
                lookup[k] = v
        n_leg11 = len(leg11_lookup)
        n_merged = sum(1 for k in leg11_lookup if k in lookup)
        print(f"  Merged {n_merged:,} Leg 11 entries from Wikipedia lookup"
              f" ({n_leg11:,} total)")

    # Build surname reverse index for O(1) lookups
    surname_map = defaultdict(list)
    for (fn, leg), party in lookup.items():
        surname = fn.split()[-1] if " " in fn else fn
        surname_map[surname].append((leg, party))

    surname_idx = {}
    for surname, entries in surname_map.items():
        leg_parties = defaultdict(set)
        for leg, party in entries:
            leg_parties[leg].add(party)
        # Store: if all same party in a leg, store that party; if mixed, store None
        surname_idx[surname] = {
            leg: (list(parties)[0] if len(parties) == 1 else None)
            for leg, parties in leg_parties.items()
        }

    return {"lookup": lookup, "surname_idx": surname_idx}


def load_senateurs() -> dict:
    """Load cached senateurs lookup from disk.

    Returns a dict with the same structure as load_deputes():
      - "lookup": {(norm_name, year): group_name}
      - "surname_idx": {surname: {year: party_or_None}}
    """
    if not SENATEURS_CACHE.exists():
        print("  WARNING: senateurs_lookup.json not found — "
              "run resolve_speakers/build_senat_lookup.py first")
        return {"lookup": {}, "surname_idx": {}}
    with open(SENATEURS_CACHE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    lookup = {tuple(k.split("||")): v
              for k, v in raw.get("lookup", {}).items()}
    surname_idx = raw.get("surname_idx", {})
    return {"lookup": lookup, "surname_idx": surname_idx}


def _normalise_name_key(raw_name: str) -> str:
    """Normalise a speaker name for lookup matching.

    Steps:
      - Strip "M." / "Mme" prefix
      - Normalise whitespace
      - Lowercase
    """
    name = raw_name.strip()
    name = re.sub(r"^(M\.|Mme)\s+", "", name, flags=re.IGNORECASE).strip()
    # Handle common prefixes and particles
    name = re.sub(r"\s+", " ", name).lower()
    # Remove accents for fuzzy matching
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "î": "i", "ï": "i",
        "ô": "o", "ö": "o",
        "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
        "œ": "oe",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name


def resolve_party(speaker_name: str, legislature: str,
                  depute_data: dict,
                  chamber: str = "", date: str = "",
                  senateur_data: dict = None) -> str:
    """Look up party for a speaker name and legislature (or year for Sénat).

    Strategy:
      1. Full-name match: normalise and match against lookup.
      2. Surname-only fallback: O(1) via pre-built reverse index.
         Returns "" (empty) if the surname is ambiguous (multiple
         legislators with different parties in the same period).

    For AN: uses legislature number as the lookup key.
    For Sénat: uses the session year (extracted from date) as the lookup key.

    Returns party/group name or empty string.
    """
    # Choose the right lookup based on chamber
    if chamber == "senat" and senateur_data:
        data = senateur_data
        # For Sénat, look up by year (extracted from debate date)
        lookup_key = date[:4] if (date and len(date) >= 4) else ""
    else:
        data = depute_data
        lookup_key = legislature

    if not speaker_name or not lookup_key or not data:
        return ""
    if not isinstance(data, dict) or "lookup" not in data:
        return ""

    lookup = data.get("lookup", {})
    surname_idx = data.get("surname_idx", {})

    # Strategy 1: full-name match
    key = _normalise_name_key(speaker_name)
    party = lookup.get((key, lookup_key), "")
    if party:
        return party

    # Strategy 2: surname-only fallback (O(1) via pre-built index)
    surname = key.strip()
    if " " not in surname and len(surname) > 2:
        leg_idx = surname_idx.get(surname, {})
        if lookup_key in leg_idx:
            party = leg_idx[lookup_key]
            # None means ambiguous (multiple legislators, different parties)
            return party if party is not None else ""

    return ""


# ------ PDF-level extraction ------------------------------------------------------------------------------------------------

def _is_debate_page(words: list[dict], page_num: int) -> bool:
    """Skip cover and SOMMAIRE pages."""
    if page_num == 0:
        return False
    if page_num <= 2:
        joined = " ".join(w["text"] for w in words[:30])
        if "SOMMAIRE" in joined.upper():
            return False
    return True


def _words_to_lines(words: list[dict]) -> list[list[dict]]:
    """Group word dicts into lines by y-position."""
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines = []
    current_line = [sorted_words[0]]
    for w in sorted_words[1:]:
        if w["top"] - current_line[-1]["top"] < Y_TOLERANCE:
            current_line.append(w)
        else:
            lines.append(sorted(current_line, key=lambda x: x["x0"]))
            current_line = [w]
    if current_line:
        lines.append(sorted(current_line, key=lambda x: x["x0"]))
    return lines


def _line_text(line: list[dict]) -> str:
    if not line:
        return ""
    return " ".join(w["text"] for w in line)


def _is_header_line(line: list[dict]) -> bool:
    return bool(HEADER_RE.search(_line_text(line)))


def _is_section_header(line_text: str) -> Optional[str]:
    """
    Detect ALL-CAPS section headers (debate topic titles).

    Returns the header text if matched, None otherwise.
    These are debate topics like "INSERTION PROFESSIONNELLE DES HANDICAPÉS"
    that appear before the relevant speeches.
    """
    stripped = line_text.strip()
    if not stripped:
        return None
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) < 5:
        return None
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio < 0.8:
        return None
    if SPEAKER_TURN_RE.match(stripped):
        return None
    if PRESIDENT_INTRO_RE.match(stripped):
        return None
    # Exclude page-header lines that leak into debate_title
    if PAGE_HEADER_RE.match(stripped):
        return None
    if len(stripped) > 150:
        return None
    return stripped


def _detect_columns(words: list[dict]) -> Optional[float]:
    """Return x-coordinate of column boundary via density-minimum scan."""
    if not words:
        return None
    page_w = max(w["x1"] for w in words)
    candidates = set()
    for w in words:
        for edge in (w["x0"], w["x1"]):
            if page_w * 0.30 < edge < page_w * 0.70:
                candidates.add(int(edge))
    if len(candidates) < 5:
        return page_w / 2
    best_x = None
    min_crossings = float("inf")
    for x in sorted(candidates):
        crossings = sum(1 for w in words if w["x0"] < x < w["x1"])
        if crossings < min_crossings:
            min_crossings = crossings
            best_x = x
    if best_x is None or min_crossings > 2:
        return page_w / 2
    return float(best_x)


def _extract_metadata(words_page0: list[dict], path: Path) -> dict:
    """Extract date, legislature, chamber, session_type from page 0."""
    text = " ".join(w["text"] for w in words_page0)
    result = {"date": "", "legislature": "", "chamber": "", "session_type": "ordinaire"}
    fname = path.name
    if "SÉNAT" in text or "SENAT" in text or fname.startswith("S_"):
        result["chamber"] = "senat"
    else:
        result["chamber"] = "assemblee_nationale"
    leg_match = re.search(r"(\d+)\s*e\s*L[ée]gislature", text, re.IGNORECASE)
    if not leg_match:
        leg_match = re.match(r"(\d+)_", path.name)
    if leg_match:
        result["legislature"] = leg_match.group(1)
    elif fname.startswith("S_"):
        result["legislature"] = "S"
    if "extraordinaire" in path.name.lower():
        result["session_type"] = "extraordinaire"
    date_match = re.search(
        rf"[Ss][ée]ance[s]?\s+du\s+\w+di\s+(\d{{1,2}})\s+({MONTHS_PATTERN})\s+(\d{{4}})",
        text, re.IGNORECASE,
    )
    if not date_match:
        date_match = re.search(
            rf"S[ÉE]ANCE\s+DU\s+(\d{{1,2}})\s+({MONTHS_PATTERN})\s+(\d{{4}})",
            text, re.IGNORECASE,
        )
    if date_match:
        day, month, year = date_match.group(1), date_match.group(2), date_match.group(3)
        month_num = MONTH_MAP.get(month.lower().replace("é", "e").replace("û", "u"), 0)
        result["date"] = f"{year}-{month_num:02d}-{int(day):02d}"
    return result


def _extract_page_columns(words: list[dict]) -> list[list[dict]]:
    """Split page words into columns if multi-column detected."""
    col_boundary = _detect_columns(words)
    if col_boundary is None:
        return [words]
    left = [w for w in words if (w["x0"] + w["x1"]) / 2 < col_boundary]
    right = [w for w in words if (w["x0"] + w["x1"]) / 2 >= col_boundary]
    return [left, right]


# ------ Speaker-turn segmentation (Option A) --------------------------------------------------------------

def _segment_speeches(lines: list[str], metadata: dict,
                      depute_lookup: dict = None,
                      senateur_lookup: dict = None) -> list[SpeechRecord]:
    """
    State-machine segmentation of lines into speaker turns.

    Option A behaviour:
      - debate_title: captured from ALL-CAPS section headers
      - speaker_name: stripped of "M." / "Mme" prefix
      - speaker_role: extracted from trailing comma-separated affiliation
      - speaker_party: resolved from depute_lookup (AN) or senateur_lookup (Sénat)
    """
    speeches = []
    current_speaker = None
    current_role = ""
    current_text = []
    current_page = 0
    next_expected = None
    current_debate_title = ""

    # President title tracking: who is the current president?
    # This is set when "M. le président" or "Mme la présidente" appears
    president_name = ""

    def _flush():
        nonlocal current_speaker, current_role, current_text
        if current_speaker and current_text:
            full_text = " ".join(current_text).strip()
            if full_text and len(full_text) > 10:
                cleaned_name = current_speaker.strip()
                role = current_role
                name = cleaned_name
                role_match = NAME_ROLE_SPLIT_RE.match(cleaned_name)
                if role_match:
                    name = role_match.group(1).strip()
                    role = role_match.group(2).strip() or role

                # Option A: strip "M." / "Mme" prefix from speaker_name
                speaker_name = re.sub(
                    r"^(M\.|Mme)\s+", "", name, flags=re.IGNORECASE
                ).strip()

                # Option B: resolve party
                party = ""
                chamber = metadata.get("chamber", "")
                date = metadata.get("date", "")
                if depute_lookup or senateur_lookup:
                    party = resolve_party(
                        speaker_name, metadata.get("legislature", ""),
                        depute_lookup,
                        chamber=chamber, date=date,
                        senateur_data=senateur_lookup,
                    )

                speeches.append(SpeechRecord(
                    speaker_name=speaker_name,
                    speaker_party=party,
                    speech=full_text,
                    debate_title=current_debate_title,
                    date=metadata.get("date", ""),
                    legislature=metadata.get("legislature", ""),
                    chamber=metadata.get("chamber", ""),
                    session_type=metadata.get("session_type", ""),
                    speaker_role=role,
                    page=current_page,
                ))
        current_speaker = None
        current_role = ""
        current_text = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_text:
                current_text.append("")
            continue

        # Option A: capture debate_title from ALL-CAPS section headers
        header_text = _is_section_header(stripped)
        if header_text:
            current_debate_title = header_text
            continue  # Don't include the header line in speech text

        # Check for president's introduction (procedural — don't record as speech)
        intro_match = PRESIDENT_INTRO_RE.match(stripped)
        if intro_match:
            _flush()
            # Track who the president is calling to speak next
            if "président" in stripped.lower() or "president" in stripped.lower():
                pres_match = re.search(
                    r"(M\.|Mme)\s+([A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŸ][a-zàâäéèêëîïôöùûüçÿœæ]+(?:\s+[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŸ][a-zàâäéèêëîïôöùûüçÿœæ]+)*)\.",
                    stripped
                )
                if pres_match:
                    next_expected = f"{pres_match.group(1)} {pres_match.group(2)}"
            continue

        # Check for speaker turn
        speaker_match = SPEAKER_TURN_RE.match(stripped)
        if speaker_match:
            prefix = speaker_match.group(1).strip()
            name_part = speaker_match.group(2).strip()
            remaining = stripped[speaker_match.end():].strip()

            lower_name = name_part.lower()
            if "président" in lower_name or "president" in lower_name:
                if current_text:
                    current_text.append(stripped)
                continue

            if next_expected:
                next_expected = None

            _flush()
            current_speaker = f"{prefix} {name_part}"
            current_text = [remaining] if remaining else []
            continue

        # Continuation line
        if current_speaker and not current_text:
            if "," in stripped and not stripped.rstrip().endswith("."):
                # Only treat as role if line is short and doesn't look like speech
                # (no speech-signalling words, no sentence-like structure)
                if (len(stripped) < 80
                        and not re.search(
                            r"\b(que|qui|dans|pour|avec|sur|est|sont|soit|cas"
                            r"|fait|peut|doit|ainsi|alors|donc|aussi|très"
                            r"|bien|plus|moins|après|avant|contre|entre|selon"
                            r"|présente|projet|loi|relatif|actuellement"
                            r"|je|vous|nous|ne|pas|madame|monsieur"
                            r"|comprends|comprenez|votre|notre|voudrais|voudriez"
                            r"|souhaite|souhaitez|pense|pensez|crois|croyez)\b",
                            stripped, re.IGNORECASE
                        )
                        and not re.search(r"[.;!?]$", stripped)):
                    current_role += (" " + stripped.rstrip(",")).strip()
                    continue
        if current_text is not None:
            current_text.append(stripped)

    _flush()
    return speeches


# ------ Cross-page merging ----------------------------------------------------------------------------------------------------

def _merge_adjacent_speeches(speeches: list[SpeechRecord]) -> list[SpeechRecord]:
    """Merge consecutive speech records where same speaker continues across pages."""
    if not speeches:
        return speeches
    merged = [speeches[0]]
    for sp in speeches[1:]:
        prev = merged[-1]
        is_procedural = prev.speaker_name == "LE PRÉSIDENT"
        if (not is_procedural
                and sp.speaker_name == prev.speaker_name
                and sp.page in (prev.page, prev.page + 1)
                and sp.speaker_role == prev.speaker_role
                and sp.debate_title == prev.debate_title):
            prev.speech = prev.speech + "\n\n" + sp.speech
            prev.page = sp.page
            # Carry forward party if one record has it but the other doesn't
            if sp.speaker_party and not prev.speaker_party:
                prev.speaker_party = sp.speaker_party
        else:
            merged.append(sp)
    return merged


def _merge_interjections(speeches: list[SpeechRecord]) -> list[SpeechRecord]:
    """Merge short interjections (<30 chars, e.g. 'Très bien!', 'Démagogue!')
    into the preceding substantive speech rather than as standalone turns."""
    if not speeches:
        return speeches
    result = []
    for sp in speeches:
        is_interjection = (
            sp.speaker_name != "LE PRÉSIDENT"
            and sp.speaker_name != ""
            and len(sp.speech) < 30
            and not re.search(
                r"\b(monsieur|madame|ministre|gouvernement|monsieur le|"
                r"je vous|nous vous|merci|question|amendement)\b",
                sp.speech, re.IGNORECASE,
            )
        )
        if is_interjection and result:
            prev = result[-1]
            prev.speech = (
                prev.speech
                + "\n(" + sp.speaker_name + ': "' + sp.speech.strip() + '")'
            )
        else:
            result.append(sp)
    return result


# ------ Single PDF extraction ----------------------------------------------------------------------------------------------

def extract_pdf(pdf_path: Path, metadata_override: Optional[dict] = None,
                depute_lookup: dict = None,
                senateur_lookup: dict = None) -> list[SpeechRecord]:
    """Extract structured speech records from a single PDF."""
    speeches = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page0_words = pdf.pages[0].extract_words(x_tolerance=1) if pdf.pages else []
        metadata = _extract_metadata(page0_words, pdf_path)
        if metadata_override:
            metadata.update(metadata_override)

        for page_idx, page in enumerate(pdf.pages):
            words = page.extract_words(x_tolerance=1)
            if not words:
                continue
            if not _is_debate_page(words, page_idx):
                continue

            columns = _extract_page_columns(words)
            if len(columns) == 1:
                all_lines = _words_to_lines(words)
            else:
                # Process columns sequentially (left first, then right)
                # so column contents are not interleaved
                all_lines = []
                for col_words in columns:
                    all_lines.extend(_words_to_lines(col_words))

            text_lines = []
            for line in all_lines:
                if _is_header_line(line):
                    continue
                line_text = _line_text(line)
                if line_text.strip():
                    text_lines.append(line_text)

            page_speeches = _segment_speeches(
                text_lines, metadata, depute_lookup, senateur_lookup
            )
            for sp in page_speeches:
                sp.page = page_idx + 1
            speeches.extend(page_speeches)

    speeches = _merge_adjacent_speeches(speeches)
    speeches = _merge_interjections(speeches)
    return speeches


# ------ Batch processing ------------------------------------------------------------------------------------------------

def extract_pdfs(pdf_paths: list[Path], depute_lookup: dict = None,
                 senateur_lookup: dict = None,
                 append_path: Optional[Path] = None,
                 log_path: Optional[Path] = None) -> list[SpeechRecord]:
    """Process multiple PDFs sequentially with checkpoint-resume.

    Args:
        pdf_paths: List of PDF paths to process.
        depute_lookup: Optional AN depute->party lookup dict.
        senateur_lookup: Optional Sénat senator->group lookup dict.
        append_path: If set, append each PDF's results incrementally.
        log_path: If set, write per-file extraction log.

    Returns:
        List of all SpeechRecord instances.
    """
    all_speeches = []
    total = len(pdf_paths)

    # Load checkpoint: which PDFs have already been processed?
    done_pdfs = set()
    if log_path and log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                done_pdfs.add(row["pdf_path"])
    elif append_path and append_path.exists():
        # Infer done PDFs from existing output
        # (This is approximate -- extraction log is preferred)
        pass

    # Prepare append file
    if append_path and not append_path.exists():
        append_path.parent.mkdir(parents=True, exist_ok=True)
        with open(append_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=SPEECH_FIELDS)
            writer.writeheader()

    # Prepare log file
    log_rows = []
    if log_path and not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_rows.append({
            "pdf_path": "", "status": "", "num_speeches": "",
            "duration_sec": "", "error": "",
        })

    for i, path in enumerate(pdf_paths):
        # Checkpoint: skip already-processed PDFs
        path_str = str(path)
        if path_str in done_pdfs:
            print(f"[{i+1:3d}/{total}] {path.name}: SKIPPED (already processed)")
            continue

        start = time.time()
        try:
            speeches = extract_pdf(path, depute_lookup=depute_lookup,
                                   senateur_lookup=senateur_lookup)
            all_speeches.extend(speeches)
            n = len(speeches)
            duration = time.time() - start
            print(f"[{i+1:3d}/{total}] {path.name}: {n} speeches ({duration:.1f}s)")

            # Incremental append
            if append_path:
                with open(append_path, "a", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=SPEECH_FIELDS)
                    for sp in speeches:
                        row = asdict(sp)
                        del row["page"]
                        writer.writerow(row)

            # Log entry
            log_rows.append({
                "pdf_path": path_str,
                "status": "OK",
                "num_speeches": str(n),
                "duration_sec": f"{duration:.1f}",
                "error": "",
            })

        except Exception as e:
            duration = time.time() - start
            print(f"[{i+1:3d}/{total}] {path.name}: ERROR -- {type(e).__name__}: {e}")
            log_rows.append({
                "pdf_path": path_str,
                "status": "ERROR",
                "num_speeches": "0",
                "duration_sec": f"{duration:.1f}",
                "error": f"{type(e).__name__}: {e}",
            })

        # Write/update log after each file (in case of crash)
        if log_path and log_rows:
            with open(log_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "pdf_path", "status", "num_speeches", "duration_sec", "error",
                ])
                writer.writeheader()
                writer.writerows(log_rows)

    return all_speeches


# ------ Inventory loading ------------------------------------------------------------------------------------------------

def load_inventory() -> list[dict]:
    """Load all PDF rows from both inventories."""
    rows = []

    # AN inventory
    if AN_INVENTORY.exists():
        with open(AN_INVENTORY, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                # Derive local PDF path from URL
                url = r["url"]
                leg = r["legislature"]
                session_key = r.get("session", "")
                pdf_name = url.rsplit("/", 1)[-1] if "/" in url else ""
                # Find the PDF on disk
                pdf_path = _find_pdf(leg, session_key, pdf_name)
                if pdf_path:
                    rows.append({"path": pdf_path, "legislature": leg, "chamber": "assemblee_nationale"})

    # Sénat inventory
    if SENAT_INVENTORY.exists():
        with open(SENAT_INVENTORY, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                url = r["url"]
                if not url.endswith(".pdf"):
                    continue  # HTML-era, skip
                pdf_name = url.rsplit("/", 1)[-1]
                # Sénat PDFs: S_{date}.pdf
                pdf_path = PDF_DIR / f"S_{pdf_name}"
                if pdf_path.exists():
                    rows.append({"path": pdf_path, "legislature": "S", "chamber": "senat"})

    return rows


def _find_pdf(leg: str, session_key: str, pdf_name: str) -> Optional[Path]:
    """Find a PDF on disk matching the inventory entry."""
    # Try Leg 11 pattern: {leg}_{session}_{pdf_name}
    if session_key:
        candidate = PDF_DIR / f"{leg}_{session_key}_{pdf_name}"
        if candidate.exists():
            return candidate
    # Try standard pattern: {leg}_{pdf_name}
    candidate = PDF_DIR / f"{leg}_{pdf_name}"
    if candidate.exists():
        return candidate
    # Try just the pdf_name
    candidate = PDF_DIR / pdf_name
    if candidate.exists():
        return candidate
    # Try Sénat pattern
    candidate = PDF_DIR / f"S_{pdf_name}"
    if candidate.exists():
        return candidate
    # Fallback: glob search
    import glob as glob_mod
    matches = list(glob_mod.glob(str(PDF_DIR / f"{leg}_*{pdf_name}")))
    if matches:
        return Path(matches[0])
    matches = list(glob_mod.glob(str(PDF_DIR / f"*{pdf_name}")))
    if matches:
        return Path(matches[0])
    return None


# ------ Test batch ----------------------------------------------------------------------------------------------------------------

TEST_SAMPLES = {
    "Leg 11 pre-1998": "data/pdfs/11_11-1997-1998-ordinaire1_094.pdf",
    "Leg 11 1998+": "data/pdfs/11_11-1999-2000-ordinaire1_013.pdf",
    "Leg 12": "data/pdfs/12_20050021.pdf",
    "Leg 13": "data/pdfs/13_20080089.pdf",
    "Leg 14": "data/pdfs/14_20130106.pdf",
    "Leg 17": "data/pdfs/17_premiere-seance-du-lundi-19-mai-2025.pdf",
    "Sénat": "data/pdfs/S_s20160317.pdf",
}


def _run_test_batch(depute_lookup: dict = None, senateur_lookup: dict = None):
    """Run extraction on the 7-PDF test batch and print results."""
    print("=" * 70)
    print("TEST BATCH -- Option A + B extraction on 7 PDFs")
    print("=" * 70)

    all_speeches = []
    by_era = {}

    for era_label, path_str in TEST_SAMPLES.items():
        path = Path(path_str)
        if not path.exists():
            print(f"\n  {era_label}: MISSING -- {path_str}")
            continue
        print(f"\n  {'-'*60}")
        print(f"  {era_label}")
        print(f"  {'-'*60}")
        try:
            speeches = extract_pdf(path, depute_lookup=depute_lookup,
                                   senateur_lookup=senateur_lookup)
            by_era[era_label] = speeches
            all_speeches.extend(speeches)
            print(f"  Speeches: {len(speeches)}")

            # Sample output
            if speeches:
                s = speeches[0]
                print(f"  First speaker: \"{s.speaker_name}\"")
                print(f"  Party: \"{s.speaker_party}\"")
                print(f"  Debate title: \"{s.debate_title[:80] if s.debate_title else '(none)'}\"")
                print(f"  Role: \"{s.speaker_role}\"")
                print(f"  Speech preview: \"{s.speech[:100]}...\"")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

    # Summary table
    print(f"\n  {'='*60}")
    print(f"  SUMMARY")
    print(f"  {'='*60}")
    print(f"  {'Era':<20} {'Speeches':>10} {'With Party':>12} {'With Title':>12}")
    print(f"  {'-'*54}")
    total_with_party = 0
    total_with_title = 0
    for era_label, speeches in sorted(by_era.items()):
        n = len(speeches)
        wp = sum(1 for s in speeches if s.speaker_party)
        wt = sum(1 for s in speeches if s.debate_title)
        total_with_party += wp
        total_with_title += wt
        print(f"  {era_label:<20} {n:>10} {wp:>12} {wt:>12}")
    print(f"  {'-'*54}")
    print(f"  {'TOTAL':<20} {len(all_speeches):>10} {total_with_party:>12} {total_with_title:>12}")

    # Party match rate
    an_speeches = [s for s in all_speeches if s.chamber == "assemblee_nationale"]
    senat_speeches = [s for s in all_speeches if s.chamber == "senat"]
    if an_speeches:
        matched = sum(1 for s in an_speeches if s.speaker_party)
        print(f"\n  AN party match rate: {matched}/{len(an_speeches)} = {matched/len(an_speeches)*100:.1f}%")
    if senat_speeches:
        matched = sum(1 for s in senat_speeches if s.speaker_party)
        print(f"  Sénat party match rate: {matched}/{len(senat_speeches)} = {matched/len(senat_speeches)*100:.1f}%")
        print(f"  Sénat speeches extracted: {len(senat_speeches)}")

    # Sample debate titles
    print(f"\n  {'-'*60}")
    print(f"  SAMPLE DEBATE TITLES")
    print(f"  {'-'*60}")
    seen_titles = set()
    for s in all_speeches:
        if s.debate_title and s.debate_title not in seen_titles:
            seen_titles.add(s.debate_title)
            print(f"  - {s.debate_title[:100]}")
    if not seen_titles:
        print(f"  (no debate titles found)")

    # Write test output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    test_csv = OUTPUT_DIR / "test_batch.csv"
    write_speeches_csv(all_speeches, test_csv)
    print(f"\n  Full output written to {test_csv}")


# ------ CSV output ----------------------------------------------------------------------------------------------------------------

def write_speeches_csv(speeches: list[SpeechRecord], output_path: Path):
    """Write speeches to CSV with the Option A schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SPEECH_FIELDS)
        writer.writeheader()
        for sp in speeches:
            row = asdict(sp)
            del row["page"]
            writer.writerow(row)
    print(f"  Wrote {len(speeches)} speeches to {output_path}")


# ------ Main --------------------------------------------------------------------------------------------------------------------------------

def main():
    # Reconfigure stdout for Windows terminals to prevent UnicodeEncodeError
    if sys.stdout and getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    if "--fetch-deputes" in sys.argv:
        fetch_deputes()
        return

    is_test = "--test" in sys.argv

    # Load depute lookup (Option B)
    print("Loading deputes lookup...")
    try:
        depute_lookup = load_deputes()
        n_lookups = len(depute_lookup["lookup"]) if "lookup" in depute_lookup else 0
        print(f"  Loaded {n_lookups:,} depute->party mappings")
    except Exception as e:
        print(f"  WARNING: Could not load deputes: {e}")
        depute_lookup = {}

    # Load senateurs lookup (Option B for Sénat)
    print("Loading senateurs lookup...")
    try:
        senateur_lookup = load_senateurs()
        n_senat = len(senateur_lookup["lookup"]) if "lookup" in senateur_lookup else 0
        print(f"  Loaded {n_senat:,} senator->group mappings")
    except Exception as e:
        print(f"  WARNING: Could not load senateurs: {e}")
        senateur_lookup = {}

    if is_test:
        _run_test_batch(depute_lookup, senateur_lookup)
        return

    # Full-corpus mode
    print("\nLoading inventory...")
    rows = load_inventory()
    print(f"  Found {len(rows)} PDFs in inventory")

    pdf_paths = [r["path"] for r in rows]
    print(f"  Processing {len(pdf_paths)} PDFs...")

    all_speeches = extract_pdfs(
        pdf_paths,
        depute_lookup=depute_lookup,
        senateur_lookup=senateur_lookup,
        append_path=SPEECHES_PATH,
        log_path=EXTRACTION_LOG,
    )

    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Total speeches: {len(all_speeches)}")
    print(f"  Output: {SPEECHES_PATH}")
    print(f"  Log: {EXTRACTION_LOG}")


if __name__ == "__main__":
    main()
