#!/usr/bin/env python3
"""
resolve_speakers.py — Resolve speaker names to canonical identities and parties.

TODO: This module is a STUB. The speaker resolution logic has not yet been
implemented. This is an UNSOLVED DESIGN PROBLEM — do not implement without
discussion.

What this module should eventually do:

    1. Accept a list of (speaker_name, chamber, date) tuples extracted from
       debate PDFs.
    2. Match each name against an official roster:
       - Assemblée nationale: deputies' roster from data.assemblee-nationale.fr
       - Sénat: senators' roster from data.senat.fr
    3. Return canonical speaker ID, normalized name (LASTNAME Firstname),
       and party affiliation at the time of the session.

Key design challenges (OPEN — decisions pending):

    A) Party changes over time: a deputy may sit in multiple groups within
       a single legislature. The resolution must be date-sensitive.
    B) Name variants: the same speaker appears as "DUPONT Jean",
       "M. Jean Dupont", "Jean Dupont", etc. across different source formats.
       A fuzzy matching strategy (e.g. rapidfuzz) is likely needed, but the
       tolerance threshold is a design decision.
    C) Roster completeness: official AN/Sénat open data rosters have gaps
       for substitute deputies (suppléants) and very short-term replacements.
    D) Multi-chamber: deputies and senators use different ID systems.
       The resolution strategy may differ between chambers.

Status: 🔴 STUB — NOT IMPLEMENTED (open design question)
"""

if __name__ == "__main__":
    print("❌ resolve_speakers.py is a stub — not yet implemented.")
    print("   This is an open design problem — see STATUS.md and METHODOLOGY.md.")
