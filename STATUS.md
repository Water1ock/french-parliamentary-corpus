# STATUS — French Parliamentary Corpus

## DONE

### Assemblée nationale URL discovery

- [x] **Legislature XI** (1997–2002) — archives subdomain, numbered PDFs
  - ✅ 6 sessions mapped (5 ordinaire + 1 extraordinaire)
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

- [x] **Total verified: 7,845 PDF URLs** confirmed returning `application/pdf` content

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

### Sénat URL discovery (`inventory/build_url_inventory.py:discover_senat_urls`)

- [ ] **Blocked on:** Sénat site structure mapping
- [ ] **Known so far:**
  - Monthly index pattern: `/seances/s{YYYYMM}/`
  - Indexes ≥2003 return 200; indexes <2003 return 403
  - Session link patterns differ by era (s{YYYYMMDD} vs sc{YYYYMMDD})
  - PDF URL derivation not yet determined
- [ ] **Next step:** Read accessible monthly index, inspect session page HTML,
      determine PDF URL pattern

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
| AN PDF URLs discovered | 7,845 |
| AN legislatures covered | XI–XVII (1997–2026) |
| AN sessions mapped | 52 |
| Sénat coverage | 🔴 PENDING |
| Speeches extracted | 🔴 PENDING (extraction not yet implemented) |
| Speaker resolutions | 🔴 PENDING (open design problem) |
