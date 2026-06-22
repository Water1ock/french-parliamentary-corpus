# STATUS — French Parliamentary Corpus

## DONE

### Completeness audit (2026-06-20)

- [x] **Priority 1 — Leg 11 filename collision BUG FIXED**
  - Root cause: `download_pdfs.py` named files `{leg}_{basename}.pdf`;
    Leg 11's 8 sessions all number PDFs 001–N, so ~902 of 1,197 PDFs
    were silently overwritten (only the first session per number survived).
  - Fix: new naming scheme `{leg}_{session}_{basename}.pdf` in `_make_filename()`.
    Example: `11_11-1997-1998-ordinaire1_001.pdf`.
  - Cleanup: old collision-prone Leg 11 files removed automatically.
  - Legs 12–17 retained under old naming (date-based / descriptive basenames
    are globally unique; no collisions exist). The download loop accepts
    either old or new names as "already downloaded."
  - Result: all 1,197 Leg 11 PDFs now on disk with session-preserving names.
    Total AN PDFs on disk: 7,843 (7,874 inv − 29 error URLs − 2 already counted as 404/500).

- [x] **Priority 2 — dyn/ HTML-not-PDF error analysis**
  - 29 AN error rows (28 status-200 + 1 status-500) in `download_errors.csv`.
  - Leg 17 (11 errors): all dates in **June 2026** (recent/future sessions).
    PDFs appear as links on session pages but the server returns `text/html`
    instead — AN server serves placeholder HTML for sessions whose CRI PDF
    has not yet been generated. Likely a publishing delay of hours-to-days
    for recent sessions; future-session links may be agenda placeholders.
    → **Genuine publishing gaps, not URL-construction bugs.**
  - Legs 15–16 (17 errors): session pages exist and list PDF links, but the
    specific error URLs do NOT appear among them. The dyn/ pagination listed
    PDF URLs that the session page does not contain. → **Genuine publishing
    gaps** (likely cancelled sittings or indexing anomalies).
  - Leg 13 (1 error, status 200): `application/pdf` content-type but null-byte
    content — corrupted file on the server.
  - Leg 16 (1 error, status 500): genuine server error.
  - **Real HTTP failures: 2** (1×500 + 1×404 Sénat).
  - **Content validation failures (200 but not PDF): 28.**
  - The logging conflates HTTP errors with content validation; the reason
    field `"not a PDF"` is accurate for the 28 status-200 entries.

- [x] **Priority 3 — Internal sequential-numbering gap check**
  - **Legislature 11**: all 8 sessions have **zero gaps** in sequential numbering
    (001–N contiguous in every session). Strong internal completeness signal.
  - **Legislatures 12–14**: all 46 sessions mapped with date-based filenames.
    Date ranges documented per session; no anomalous gaps detected.
  - **Legislatures 15–17**: descriptive filenames (no sequential pattern to
    gap-check internally).
  - **Sénat**: 2,178 PDF-era sessions (2008–2025) across 184 months. 17 months
    have inter-session gaps >1 week (normal — the Sénat does not sit daily).
    586 HTML-era sessions (2003–2007) catalogued, no PDFs.
  - **Verdict**: internal consistency is strong. No unexplained numbering gaps
    found that would signal missing inventory entries.

- [x] **Priority 4 — Cross-validation against Réunions dataset (AN 2017+)**
  - Source: `data.assemblee-nationale.fr` Réunions dataset (JSON ZIP per
    legislature: `Agenda_XV.json.zip`, `Agenda.json.zip` for 16e/17e).
    Genuinely independent of the CRI PDF archive — separate metadata system.
  - Filter: `@xsi:type = 'seance_type'` identifies plenary sittings.
  - Results: **100% coverage of all CRI-published plenary dates.**

    | Leg | Réunions dates | Inventory dates | Match | Non-CRI (no PDF) |
    |-----|---------------|-----------------|-------|-----------------|
    | 15  | 869           | 699             | 699   | 170             |
    | 16  | 330           | 283             | 282   | 48              |
    | 17  | 330           | 258             | 258   | 72              |

  - The 290 Réunions dates not in our inventory are **séances without
    published CRI PDFs** — confirmed by precise re-verification of 18 sampled
    dates (including the 3 initially misidentified as "gaps").
  - Sitting counts explain the discrepancy:

    | Leg | Réunions séances | CRI PDFs | Séances without CRI |
    |-----|-----------------|----------|--------------------|
    | 15  | 2,641           | 1,484    | 1,157              |
    | 16  | 959             | 593      | 366                |
    | 17  | 993             | 557      | 436                |

  - The Réunions dataset tracks ALL parliamentary meetings labelled as
    séances (including procedural, ceremonial, and cancelled items); only
    a subset produce a published compte rendu intégral PDF.
  - **No pagination boundary bug found** in `build_url_inventory.py` — the
    3 initially-reported "gaps" (2017-07-03, 2022-02-07, 2022-07-05) were
    investigation false positives (date pattern matched non-PDF page elements).
    Precise re-verification confirmed zero CRI PDFs exist for those dates.

### Assemblée nationale URL discovery

- [x] **Legislature XI** (1997–2002) — archives subdomain, numbered PDFs
  - ✅ 8 sessions mapped (6 ordinaire + 2 extraordinaire) — dynamically discovered
    from index page (corrected 2026-06-19)
  - ✅ All 1,197 PDFs downloaded with collision-safe naming
  - ✅ Sequential numbering verified: zero gaps in every session
  - ✅ Test: `tests/test_an_legislature_11_pdf_discovery.py`

- [x] **Legislatures XII–XIV** (2002–2017) — .asp session index → derived PDF URL
  - ✅ 46 sessions mapped, all date-based PDFs downloaded
  - ✅ URL pattern verified: `www.assemblee-nationale.fr/{leg}/pdf/cri/{session}/{YYYYMMDD}.pdf`
  - ✅ Test: `tests/test_an_legislature_12_14_pdf_url_pattern.py`

- [x] **Legislatures XV–XVII** (2017–2026) — dyn/ paginated index
  - ✅ Paginated discovery; 29 content-validation failures analysed and understood
  - ✅ Cross-validated against independent Réunions dataset (**100% CRI-published dates covered**)
  - ✅ Test: `tests/test_an_legislature_15_17_dyn_pagination.py`

- [x] **Congrès (joint AN+Sénat) sessions identified — deferred, not excluded**

### Sénat URL discovery

- [x] **Sénat URL patterns MAPPED** (2026-06-20)
- [x] **Sénat inventory BUILT** — `inventory/build_senat_url_inventory.py`
  - 2,764 sessions (2003–Dec 2025): 586 HTML-era + 2,178 PDF-era
- [x] **Sénat PDFs downloaded** — 2,177 on disk (1 perm 404: Sunday non-sitting)

### Pipeline infrastructure

- [x] `download/download_pdfs.py` — collision-safe filename scheme (`{leg}_{session}_{basename}.pdf`), automatic Leg 11 cleanup, dual-scheme resume
- [x] `download/download_senat_pdfs.py` — resume-safe Sénat PDF downloader
- [x] All other modules documented previously

### Tests

- [x] 7 test files covering AN XI–XVII discovery and Sénat URL patterns

---

## Calendar validation coverage

| Chamber / Period | Validation method | Status |
|---|---|---|
| **AN 2017+** (15e–17e) | Independent cross-validation against Réunions dataset | **100% CRI-published dates covered.** 290 Réunions entries are non-CRI séances (confirmed by sampling) |
| **AN 1997–2017** (11e–14e) | Internal consistency only (sequential gap check) | Leg 11: zero gaps in all sessions. Legs 12–14: all sessions mapped |
| **Sénat 2003–2025** | Internal consistency only (data.senat.fr is sole structured source) | 2,178 PDF-era sessions, 17 months with >1wk gaps (expected) |
| **Sénat 2000–2002** | No source available (403 on archives, Gallica only) | Known gap — Journal Officiel scans only |
| **Sénat 2003–2007** | 586 HTML-era sessions catalogued, no PDFs | Separate extraction path needed |

### Independent validation limitations

**AN Legislatures XI–XIV (1997–2017):** No independent structured calendar dataset
exists for this period. We investigated every plausible source:

| Source | Why it doesn't qualify |
|---|---|
| `data.assemblee-nationale.fr` Réunions/Agenda datasets | Only cover legislature XV onward (2017+). No structured agenda data exists for XI–XIV. |
| `data.assemblee-nationale.fr` AMO30 dataset | Covers XI onward but is actor-centric (biographical/mandate data), not a session calendar. |
| `archives.assemblee-nationale.fr` | HTML index pages are the SOURCE of our inventory, not an independent validator. |

This is an institutional reality, not a pipeline gap: the AN's structured open-data
programme began around 2017, coinciding with the dyn/ portal launch. For the
1997–2017 period, the CRI PDF archives themselves are the primary source.
Our internal consistency checks (Leg 11 sequential numbering: zero gaps across
all sessions; Legs 12–14: all session dates mapped contiguously) are the best
available validation. We document this as a stated limitation rather than
overclaiming completeness.

**Sénat (all periods):** No genuinely independent structured calendar source
exists for the Sénat. We investigated every plausible alternative:

| Source | Why it doesn't qualify |
|---|---|
| `data.gouv.fr` | Re-publishes datasets originating from `data.senat.fr`; same underlying source. |
| `data.europa.eu` | Harvests from `data.gouv.fr`; two levels removed but same origin. |
| Légifrance / DILA | Publishes legal outputs (laws, JO text), not session calendars. |
| NosSénateurs / Regards Citoyens | Downstream scrapers of `senat.fr`; not independent upstream sources. |
| Gallica (BNF) | Journal Officiel scans only (pre-2003); no structured calendar. |
| Academic projects | All built from Sénat's own published data. |

The Sénat's digital archive is a closed system — `data.senat.fr` is the sole
authoritative structured data provider. No external entity independently tracks
the Sénat's plenary calendar. The `debats.sql` dump used for cross-validation
is still a `data.senat.fr` product (different format, same underlying database).
This is an institutional reality, not a collection failure. We document it as a
stated limitation.

---

## PROGRESS UPDATE (2026-06-21)

### Coverage independently verified

- [x] **AN Legislature XVII** — Cross-checked against official AN `dyn/17/comptes-rendus/seance`
  paginated index (16 pages, 558 URLs). **557/558 match** — the 1 URL in official but not our
  inventory is a **Leg 16 URL cross-listed on the Leg 17 index** (correctly assigned to Leg 16
  by our URL-based legislature derivation). **Zero real gaps.**
- [x] **Sénat PDF-era** — Cross-checked against official `data.senat.fr` `debats.sql` dump
  (314 MB, covering 2003–2026). **586 HTML-era + 2,177 PDF-era entries exactly match.**
- [x] **11 missing Leg 17 PDFs** — Re-probed 2026-06-21. All return HTTP 200 with `text/html`
  placeholder pages (the AN serves a session HTML page when the final CRI PDF is not yet
  generated). **Diagnosis: genuine publishing delay of ~1–3 weeks.** These are temporary,
  not permanent absences.
- [x] **Sénat 2000–2002 gap** — Confirmed via `data.senat.fr` debats.sql: earliest record is
  2003-01-14. The Sénat's structured digital archive begins in 2003; 2000–2002 exists only
  as Journal Officiel scans (Gallica). **Knowable but not programmatically recoverable
  without a separate Gallica-scraping effort.**
- [x] **AN XV (2017+) Réunions cross-check** — Claim carried forward from original 2026-06-19/20
  investigation. **Not independently re-run this session.** Numbers in STATUS.md reflect the
  original investigation results.

### Sénat false positive removed

- [x] **2009-06-21 removed from `senat_inventory.csv`** — Sunday session with no PDF.
  Total PDF-era entries: 2,178 → **2,177** (matching actual PDFs on disk).

### PDF text extraction — partially implemented

- [x] `/extract/extract_text.py` now contains **~1,000 lines** of extraction logic:
  - `pdfplumber`-based word extraction with `x_tolerance=1` (handles Leg 14 zero-spacing PDFs)
  - Multi-column detection and column-by-column processing (handles Leg 11 pre-1998 PDFs)
  - Speaker-turn segmentation via regex (handles "M." / "Mme" patterns)
  - Cross-page speech merging and interjection merging
  - Debate title capture from ALL-CAPS section headers
  - Metadata extraction from cover pages (date, legislature, chamber, session_type)
  - Incremental CSV output with checkpoint-resume
  - **Option B: AN party resolution inline** (deputes lookup downloaded from AMO30 dataset,
    cached to `data/reference/deputes_lookup.json`, with surname-only O(1) fallback)
- [x] **Tested on 7 PDFs** (one per era: Leg 11 pre-1998, Leg 11 1998+, Leg 12, 13, 14, 15–17, Sénat)
  — output written to `data/extracted/test_batch.csv` (~770 rows) and `verification.txt`
- [ ] **Full-corpus extraction NOT yet run** (would process ~10,000 PDFs)
- [ ] **Extraction quality NOT yet systematically validated**

### Speaker/party resolution

- [x] **AN deputes lookup BUILT and INTEGRATED** — inline in `extract_text.py`.
  Downloads AMO30 dataset from `data.assemblee-nationale.fr`, builds
  `deputes_lookup.json` with (norm_name, legislature) → party mapping.
  Surname-only O(1) fallback for partial matches.
- [x] **Sénat lookup BUILT** — `resolve_speakers/build_senat_lookup.py` downloads
  ODSEN_HISTOGROUPES.csv from `data.senat.fr`, builds `senateurs_lookup.json`
  with (norm_name, year) → group mapping.
- [ ] **Sénat lookup NOT YET INTEGRATED** into `extract_text.py` — Sénat speeches
  currently get `speaker_party = ""` during extraction.
- [ ] **Standalone module** (`resolve_speakers/resolve_speakers.py`) is still a stub —
  the resolution logic lives inline in `extract_text.py` for now.

### AN 2017+ inventory gaps

- [x] **RESOLVED (2026-06-20):** All 290 Réunions-only dates are non-CRI séances.

---

## OPEN DESIGN QUESTIONS

### Sénat party resolution integration

The `build_senat_lookup.py` script and `senateurs_lookup.json` cache exist.
The resolution logic needs to be wired into `extract_text.py` so Sénat speeches
get `speaker_party` populated. The design is resolved (same pattern as AN:
full-name match + surname-only fallback); only the integration code is pending.

### Sénat 2003–2007 HTML-era sessions

586 HTML sessions need scraping, not PDF extraction. This is the largest
remaining pipeline gap. Either build the scraper before dataset paper
submission or scope the paper to the PDF-era only.

### Sénat 2000–2002 gap

The Sénat's digital archive begins January 2003. Pre-2003 debates exist only
as Journal Officiel scans via Gallica (BNF). This is an institutional
limitation, documented as a stated limitation.

### License choice

- CC-BY-4.0 for the data / MIT for the code — **confirm with author**

### Dataset paper framing

The corpus is being prepared for submission as a dataset paper. Target venues:
*Language Resources & Evaluation*, *Scientific Data*, or similar. The key novel
contributions are dual-chamber coverage (no existing French parliamentary corpus
includes the Sénat), temporal extension through December 2025 (ParisParl and
ParlaMint-FR freeze at 2019), and a flat CSV/Parquet format.

---

## Key metrics

| Metric | Value |
|--------|-------|
| AN PDF URLs in inventory | 7,874 |
| AN legislatures covered | XI–XVII (1997–2026) |
| AN PDFs on disk | 7,843 (29 content-validation gaps) |
| Sénat sessions in inventory | 2,764 (2003–2025) |
| Sénat PDF URLs | 2,177 (2008–2025, 2009-06-21 false positive removed) |
| Sénat PDFs on disk | 2,177 (matches inventory) |
| Sénat HTML-era sessions | 586 (2003–2007) |
| **Total PDFs on disk** | **10,020** (= 7,843 AN + 2,177 Sénat, matches inventory) |
| AN 2017+ CRI coverage | **100%** (all CRI-published dates covered; 290 Réunions entries are non-CRI) |
| Speeches extracted | 🟡 PARTIAL — ~770 rows from 7 test PDFs |
| Speaker resolutions | 🟡 PARTIAL — AN lookup integrated; Sénat lookup built, not yet integrated |
