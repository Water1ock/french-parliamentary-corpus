# Methodology — URL Discovery for Assemblée Nationale Debate PDFs

This document describes how the three distinct URL patterns for Assemblée
nationale plenary debate PDFs were discovered. This is a transparent account
of the trial-and-error process, intended to make the eventual dataset paper's
methods section credible and reproducible.

---

## Pattern 1: Legislature XI — archives subdomain, numbered PDFs

**Discovery date:** Early exploration phase.

**Starting point:** We knew the Assemblée nationale has an archives subdomain
at `archives.assemblee-nationale.fr`. The initial probe tested:

```
https://archives.assemblee-nationale.fr/11/cri/index.html
```

This returned HTTP 200 with an HTML table of session links. The index page
listed entries like:
- `11-1997-1998-ordinaire1.html`
- `11-1998-1999-ordinaire1.html`

**Key finding:**
Opening a session page (e.g. `.../11/cri/11-1997-1998-ordinaire1.html`)
revealed an HTML table with numbered links: `001.pdf`, `002.pdf`, ...

**Confirmation:**
Downloading `.../11/cri/1997-1998-ordinaire1/001.pdf` and checking the
first 4 bytes confirmed `%PDF` — these are real PDFs.

**Lesson:** For Legislature XI, the archives subdomain directly lists
numbered PDFs. No URL derivation is needed — the PDF URLs are explicit
in the session page HTML.

---

## Pattern 2: Legislatures XII–XIV — .asp session index → derived PDF URL

**Discovery date:** After finding the XI pattern, we probed XII–XIV.

**Initial assumption:** We expected the same pattern to work:
```
https://www.assemblee-nationale.fr/12/cri/2002-2003/
```

**First obstacle:** This returned **HTTP 403** — directory listing disabled.

**Probing further:** We tried the index page:
```
https://www.assemblee-nationale.fr/12/cri/2002-2003/index.asp
```
This returned HTTP 200. The page listed `<a href="20021002.asp">` links.

**Key insight:** The .asp filenames are **8-digit date codes** in YYYYMMDD
format. We hypothesised that the PDF URLs might follow the same structure
but under `/pdf/cri/` instead of `/cri/`.

**Testing the hypothesis:**
```
https://www.assemblee-nationale.fr/12/pdf/cri/2002-2003/20021002.pdf
```
→ HTTP 200, first 4 bytes `%PDF` ✅

**Derivation rule confirmed:**
For legislatures XII–XIV:
1. Scrape `/{leg}/cri/{session}/` for all `{YYYYMMDD}.asp` links
2. Derive PDF URL: `/{leg}/pdf/cri/{session}/{YYYYMMDD}.pdf`

**Why this works:**
The AN site serves session index pages through an ASP system that lists
files by date. The actual PDFs are served from `/pdf/cri/` while the
index pages are at `/cri/`. This redirection pattern was presumably
an artefact of the site's internal routing.

---

## Pattern 3: Legislatures XV–XVII — dyn/ paginated API

**Discovery date:** After XII–XIV mapping was complete.

**Initial assumption:** We expected the ASP-to-PDF derivation to work for
XV onward too:
```
https://www.assemblee-nationale.fr/15/cri/2017-2018/
```

**First obstacle:** HTTP 404 — the old `/cri/` pattern was gone.

**Searching for the new interface:**
We found that the AN's public site had a "comptes-rendus" (minutes) section
accessible through a modern URL pattern:
```
https://www.assemblee-nationale.fr/dyn/15/comptes-rendus/seance
```

This returned an HTML page listing session links.

**Key finding:** The page included pagination links like `?page=2`,
indicating a paginated index.

**Testing pagination:**
```
https://www.assemblee-nationale.fr/dyn/15/comptes-rendus/seance?page=1&limit=20
```
→ Returned HTML with `<a href="/dyn/15/comptes-rendus/seance/session-...">` links.

**Optimisation:**
The default page limit was 20, requiring many pages. Testing `&limit=100`
confirmed the API accepts this parameter, reducing requests by 5×.

**Confirmation:**
Session URLs ending in `.pdf` resolved to real PDFs.

**Key insight:**
Unlike XII–XIV, the dyn/ system produces the PDF URL directly — no
derivation step is needed. The challenge is pagination management.

---

## What did NOT work

### Direct directory listing on www subdomain
```
https://www.assemblee-nationale.fr/12/cri/       → 403
https://www.assemblee-nationale.fr/13/cri/       → 403
```
Directory listing is disabled for all legislative periods on the www subdomain.

### Direct directory listing on archives subdomain (legislatures 12+)
```
https://archives.assemblee-nationale.fr/12/cri/  → various errors
```
The archives subdomain only covers Legislature XI.

### Guessing PDF URLs (brute force)
We briefly tested whether PDF URLs followed simple patterns like
`/12/cri/2002-2003/001.pdf` — these returned 404. The `asp→pdf` derivation
was the correct approach.

---

## Positive signals — how we confirmed correctness

### PDF header check
Every discovered URL is tested by checking `response.content[:4] == b"%PDF"`.
This confirms the server is serving real PDF content, not an HTML error page
with a `.pdf` extension.

### HTTP 200 vs 403 vs 404
- **200 + %PDF** → valid PDF
- **403** → accessible but blocked (needs User-Agent or different path)
- **404** → non-existent URL

### Content-Length consistency
PDFs for the same session typically have sizes in the hundreds of KB to
low MBs. Values like 1,024 bytes indicated HTML error pages, not real PDFs.

---

## Congrès (joint sessions) — deferred, not excluded

Congrès (joint AN+Sénat) sessions are identified but NOT YET INCLUDED in this
release. One example was found during XIV session discovery
(`/14/cri/congres/20154001.asp`). This is a sequencing decision, not a
permanent scope exclusion: Congrès sessions are rare (a handful across
1997–2025, typically constitutional votes or presidential addresses) and would
require a small schema extension (a third `chamber` value, e.g. `'congres'`)
plus a dedicated discovery pass across all legislatures. This is deferred until
core AN and Sénat plenary coverage is complete, and is tracked as a planned
future addition, not ruled out.

---

## Legislature XI session-list correction (2026-06-19)

An initial hardcoded list of XI session slugs (`XI_SESSIONS` in
`build_url_inventory.py`) contained only 6 entries. Live verification against
`archives.assemblee-nationale.fr/11/cri/index.html` on 2026-06-19 returned 8
session slugs, revealing two were missing:
- `11-1996-1997-ordinaire1`
- `11-1996-1997-extraordinaire1`

The hardcoded list was replaced with dynamic discovery — scraping the index
page itself to get the real session list. This eliminates the risk of a
hand-maintained list silently drifting out of sync.

---

## Legislature XVI cross-listed PDF on Legislature XVII index (2026-06-19)

During manual verification of the dyn/ inventory, one cross-listed PDF was
found: the `/dyn/17/comptes-rendus/seance` index page (Legislature XVII,
2024–2026) includes a PDF whose URL is `/dyn/16/comptes-rendus/seance/...`
(a Legislature XVI session, 2022–2024). This is likely due to the legislature
transition after the July 2024 snap election — a session from the closing days
of Legislature XVI was listed on the following legislature's index page.

**Fix:** The `discover_legislatures_dyn()` function originally set the
`legislature` field from the outer loop variable (the index page being
scraped), meaning this PDF was incorrectly labeled legislature=17 when the
URL clearly showed legislature=16. The function now derives the legislature
number from the PDF URL itself via regex (`/dyn/(\d+)/`). If the URL's
legislature number differs from the loop variable, a warning is logged and
the URL's value is used. This ensures the inventory is authoritative even
when index pages list cross-legislature content.

---

## Remaining unknowns

### Sénat (French Senate)
The Sénat site structure has NOT been fully mapped. Preliminary exploration:
- Monthly index: `senat.fr/seances/s{YYYYMM}/`
- Accessible from ~2003 onward; 403 for earlier dates
- Session link patterns vary by year
- PDF URL derivation not yet determined

See `tests/test_coverage_gaps.py` for the current state of exploration.

### Session type extraction (ordinaire vs extraordinaire)
For legislatures XII–XIV, session types are encoded in the session slug
(e.g. `2002-2003-extra`). For XI and XV–XVII, the type needs to be
determined from the session date or metadata — not yet implemented.

### Date extraction from PDF filenames
For XII–XIV, the date is embedded in the filename (`{YYYYMMDD}.pdf`).
For XI, the date is not directly in the filename — it appears in the
session page HTML but hasn't been extracted programmatically yet.
For XV–XVII, dates are embedded in the session slug within the URL.

---

## Sénat false positive removal — 2009-06-21 (Sunday, no PDF)

**Date:** 2026-06-21 (audit)

**Situation:** The Sénat inventory (`data/senat_inventory.csv`) previously
contained an entry for 2009-06-21, derived from `data.senat.fr`'s official
`debats.sql` dump. The URL
`https://www.senat.fr/seances/s200906/s20090621/s20090621.pdf`
reliably returns HTTP 404.

**Diagnosis:** 2009-06-21 was a Sunday. The Sénat does not hold plenary
sessions on Sundays under normal circumstances. The `debats.sql` entry
likely refers to a procedural or administrative record that does not
produce a published compte rendu PDF. This is a false positive in the
data.senat.fr derived inventory.

**Action:** Removed the 2009-06-21 entry from `data/senat_inventory.csv`
on 2026-06-21. The download error log (`data/senat_download_errors.csv`)
retains the entry as a record of the investigation.

**Implication:** No coverage gap. The Sénat PDF-era total is now 2,177
URLs (was 2,178), matching the actual count of PDFs on disk.

---

## Independent validation limitations

### AN Legislatures XI–XIV (1997–2017)

No independent structured calendar dataset exists for this period. The AN's
structured open-data programme (`data.assemblee-nationale.fr`) began around
2017 with the dyn/ portal launch. The Réunions/Agenda datasets that enable
independent cross-validation for legislatures XV–XVII do not extend backward.
The AMO30 historical dataset covers XI onward but is biographical/mandate
data, not a session calendar.

For legislatures XI–XIV, the CRI PDF archives themselves are the primary source.
Our internal consistency checks provide the best available validation: sequential
numbering on Leg 11 shows zero gaps across all 8 sessions; Legs 12–14 show
contiguous date ranges per session. This is a stated limitation, not a
pipeline gap.

### Sénat (all periods)

The Sénat's digital archive is a closed institutional system. `data.senat.fr`
is the sole authoritative structured data provider. Every other source investigated
— `data.gouv.fr`, `data.europa.eu`, Légifrance, NosSénateurs/Regards Citoyens,
Gallica, and academic projects — either republishes data originally from
`data.senat.fr` or does not track session calendars at all.

The `debats.sql` dump used for cross-validating the Sénat PDF-era inventory
is still a `data.senat.fr` product — a different format (database dump vs.
scraped HTML), but the same underlying database. This provides internal
consistency verification rather than genuine independent validation.

This is an institutional reality, not a collection failure. We document it
as a stated limitation.
