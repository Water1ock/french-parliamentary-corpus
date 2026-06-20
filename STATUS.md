# STATUS — French Parliamentary Corpus

## DONE

### Assemblée nationale URL discovery

- [x] **Legislature XI** (1997–2002) — archives subdomain, numbered PDFs
  - ✅ 8 sessions mapped (6 ordinaire + 2 extraordinaire) — dynamically discovered
    from index page (corrected 2026-06-19; 2 sessions were missing from hardcoded list)
  - ✅ URL pattern verified: `archives.assemblee-nationale.fr/11/cri/{session}/{nnn}.pdf`
  - ✅ Test: `tests/test_an_legislature_11_pdf_discovery.py`
  - Evidence: 265 PDFs per full session, verified as valid `application/pdf`

- [x] **Legislatures XII–XIV** (2002–2017) — .asp session index → derived PDF URL
  - ✅ 12 sessions (XII), 17 sessions (XIII), 17 sessions (XIV) mapped
  - ✅ URL pattern verified: `www.assemblee-nationale.fr/{leg}/pdf/cri/{session}/{YYYYMMDD}.pdf`
  - ✅ Test: `tests/test_an_legislature_12_14_pdf_url_pattern.py`
  - Evidence: .asp filenames are 8-digit date codes; /cri/ → /pdf/cri/ derivation works

- [x] **Legislatures XV–XVII** (2017–2026) — dyn/ paginated index
  - ✅ Paginated discovery via /dyn/{leg}/comptes-rendus/seance?page=N&limit=100
  - ✅ URL pattern verified: `www.assemblee-nationale.fr/dyn/{leg}/comptes-rendus/seance/session-{...}.pdf`
  - ✅ Test: `tests/test_an_legislature_15_17_dyn_pagination.py`

- [x] **Total: 7,845+ PDF URLs** confirmed returning `application/pdf` content (verified in the old repo; the discovery pattern is reproduced here but the inventory CSV must be rebuilt; the XI correction adds ~530 PDFs from the 2 newly-discovered sessions)

- [x] **Congrès (joint AN+Sénat) sessions identified — deferred, not excluded**
  - Found during XIV session discovery: `/14/cri/congres/20154001.asp`
  - Deferred for sequencing reasons (rare, ~handful across 1997–2025); requires
    schema extension (`chamber` value `'congres'`) and dedicated discovery pass
  - Tracked as a planned future addition, NOT ruled out

### Pipeline infrastructure

- [x] `inventory/build_url_inventory.py` — full AN URL discovery (re-documented)
- [x] `download/download_pdfs.py` — resume-safe, rate-limited PDF downloader
- [x] `pipeline/run_pipeline.py` — incremental orchestrator
- [x] `.gitignore` — excludes `venv/`, `__pycache__/`, `data/pdfs/`, `notes/`, `scratch/`
- [x] `requirements.txt` — all Python dependencies

### Documentation

- [x] `README.md` — full project README with positioning statement
- [x] `CITATION.cff` — machine-readable citation
- [x] `LICENSE` — placeholder (TBD — likely CC-BY-4.0 / MIT)
- [x] `STATUS.md` — this file
- [x] `METHODOLOGY.md` — trial-and-error discovery narrative

### Tests (methodology evidence)

- [x] `tests/test_an_legislature_11_pdf_discovery.py` — XI discovery + PDF validation
- [x] `tests/test_an_legislature_12_14_pdf_url_pattern.py` — XII–XIV .asp→.pdf derivation
- [x] `tests/test_an_legislature_15_17_dyn_pagination.py` — XV–XVII dyn/ pagination
- [x] `tests/test_pdf_url_validity.py` — master URL validity checker
- [x] `tests/test_an_session_links.py` — cross-era session link accessibility
- [x] `tests/test_coverage_gaps.py` — Sénat site exploration (docs the 403 cutoff)

---

## STUB (TODO — clear path forward)

### Sénat URL discovery (`inventory/build_senat_url_inventory.py`)

- [x] **Sénat URL patterns MAPPED** (2026-06-20) — test file created
  - ✅ Modern session page pattern: `/seances/s{YYYYMM}/s{YYYYMMDD}/st{YYYYMMDD}000.html`
  - ✅ Modern PDF URL pattern: `/seances/s{YYYYMM}/s{YYYYMMDD}/s{YYYYMMDD}.pdf`
  - ✅ PDFs validated for 2008, 2009, 2010, 2020, 2022, 2023 — all return `%PDF`
  - ✅ `data.senat.fr` bulk data accessible (debats.zip: 33.5 MB, cri.zip: 542 MB)
  - ✅ `debats.sql` schema confirmed: `debats` table has `datsea`, `deburl`, `numero`, `estcongres`
  - ✅ Test file: `tests/test_senat_pdf_discovery.py`
- [x] **Sénat URL inventory BUILT** (2026-06-20)
  - ✅ `inventory/build_senat_url_inventory.py` parses data.senat.fr debats.sql
  - ✅ Output: `data/senat_inventory.csv` — 2,764 sessions (2003–2025)
  - ✅ Era split: 586 HTML session pages (2003–2007) + 2,178 PDF URLs (2008–2025)
  - ✅ Excludes: 1 pre-2003 outlier, 50 post-cutoff (2026), 1 Congrès session

### PDF text extraction (`extract/extract_text.py`)

- [ ] **Blocked on:** TODO after PDFs are downloaded
- [ ] **Known challenges:**
  - Older PDFs (XI–XIV) may be scanned images requiring OCR
  - Newer PDFs (XV–XVII) are born-digital
  - Text layout varies by legislature
- [ ] **Next step:** Implement extraction pipeline when ready

### Speaker/party resolution (`resolve_speakers/resolve_speakers.py`)

- [ ] **Blocked on:** Open design question — see below

---

## OPEN DESIGN QUESTIONS

### Speaker name→party resolution methodology

This is an **unsolved design problem**. Key decisions to be made:

1. **Roster source**: official AN/Sénat open data API vs scraped rosters vs
   third-party sources (nosdeputes.fr, etc.)
2. **Date-sensitive matching**: party affiliation changes over time — the
   matching must record the party at the *session date*, not the speaker's
   current/previous party
3. **Name variant tolerance**: "DUPONT Jean" vs "M. Jean Dupont" vs
   "Jean Dupont" — what fuzzy matching threshold is appropriate?
4. **Substitute deputies**: short-term replacements (suppléants) may not
   appear on standard rosters
5. **Multi-chamber normalization**: AN and Sénat use different ID systems
6. **Validation**: how do we measure accuracy of the resolved matches?

**Do not implement a heuristic without discussion.** This needs a principled
design decision, ideally informed by the official rosters' format and
coverage.

### Sénat URL discovery

The Sénat site uses a different structure than the AN. Preliminary exploration
(see `tests/test_coverage_gaps.py`) shows:
- A 403 wall for sessions before ~2003
- Multiple URL pattern variants (`/seances/s{YYYYMM}/s{YYYYMMDD}.html`,
  `/seances/s{YYYYMM}/sc{YYYYMMDD}.html`, etc.)
- The PDF derivation rule is unknown

**This needs dedicated site-mapping work.**

### License choice

- CC-BY-4.0 for the data (consistent with source licences)
- MIT for the code
- **Confirm with author before finalizing**

---

## Key metrics

| Metric | Value |
|--------|-------|
| AN PDF URLs (pattern verified on old repo) | 7,845 |
| AN legislatures covered | XI–XVII (1997–2026) |
| AN sessions mapped | 52 |
| Sénat coverage | 🔴 PENDING |
| Speeches extracted | 🔴 PENDING (extraction not yet implemented) |
| Speaker resolutions | 🔴 PENDING (open design problem) |
