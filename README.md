# French Parliamentary Corpus

A living, re-runnable pipeline that produces a flat, tabular dataset of French parliamentary plenary debates covering **both chambers** (Assemblée nationale + Sénat), **2000–2025**.

## Positioning

This corpus differs from existing resources (ParisParl, ParlaMint-FR) in four key respects:

1. **Extended temporal coverage** — spans 2000–2025, capturing two full decades of French parliamentary discourse including the most recent legislatures.
2. **Dual-chamber coverage** — includes both the Assemblée nationale and the Sénat, rather than being AN-only. This enables cross-chamber comparative analysis.
3. **Flat tabular format** — released as CSV/Parquet rather than TEI-XML. The data loads directly into pandas, R, or SQL with no parsing step, enabling immediate use for computational social science and legal research workflows.
4. **Living, re-runnable pipeline** — designed as an incremental, reproducible pipeline rather than a one-time static release. As new sessions are published, the pipeline can be re-run to extend the dataset.

### Scope

Only **plenary (full chamber) sessions** are covered. Committee/commission debates are **out of scope** for this release.

## Mandatory columns

| Column | Description |
|--------|-------------|
| `speaker_name` | Speaker's full name (LASTNAME Firstname) |
| `speaker_party` | Party affiliation at time of session |
| `speech` | Utterance text |
| `debate_title` | Agenda item or topic under discussion |
| `date` | Session date (YYYY-MM-DD) |

## Additional columns

| Column | Description |
|--------|-------------|
| `legislature` | Roman numeral (XI–XVII for AN; relevant term for Sénat) |
| `chamber` | `assemblee_nationale` or `senat` |
| `session_type` | `ordinaire` or `extraordinaire` (AN only for now) |
| `speaker_role` | `président`, `ministre`, `député`, `sénateur` (best effort) |

## Planned future additions

### Linguistic annotation (deferred — post core extraction)

Once the baseline CSV corpus is complete, we plan to add an optional
linguistically-annotated layer with the following columns:

| Annotation | Column | Description |
|---|---|---|
| **POS** (Part-of-Speech) | `speech_pos` | Grammatical role tags per token (e.g. NOUN, VERB, DET) |
| **Lemmas** | `speech_lemma` | Dictionary root form per token (e.g. "parlions" → "parler") |
| **NER** (Named Entity Recognition) | `speech_ner` | Entity spans tagged as PERSON, ORG, LOC, DATE, etc. |

This will be produced as a separate `speeches_annotated.csv` (or Parquet) file
so the baseline CSV remains dependency-free. Target library: spaCy with
`fr_core_news_lg` or Stanza with the French model. Annotation will run as a
post-processing pass after the core extraction pipeline, not inline.

These annotations are absent by design from the baseline release — our primary
audience (computational social scientists) works with raw text in pandas/R/SQL.
Users requiring linguistic annotation can also apply off-the-shelf tools
to the flat CSV output in their own workflows.

## Repository structure

```
french-parliamentary-corpus/
├── inventory/           # URL discovery scripts
│   ├── build_url_inventory.py        # AN PDF URL discovery (DONE)
│   └── build_senat_url_inventory.py  # Sénat URL discovery via data.senat.fr (DONE)
├── download/            # PDF downloaders (resume-safe)
│   ├── download_pdfs.py              # AN PDF downloader
│   └── download_senat_pdfs.py        # Sénat PDF downloader
├── extract/             # PDF text extraction (engine built + validated; full run pending)
│   └── extract_text.py              # ~1,000 lines: pdfplumber parsing, speaker-turn
│                                     # segmentation, debate title capture, AN + Sénat party lookup.
│                                     # Validated on 36 PDFs: 0 crashes, 0 page-header leaks.
├── resolve_speakers/    # Speaker→party resolution (DONE)
│   ├── build_senat_lookup.py        # Sénat speaker→party lookup builder (DONE)
│   └── resolve_speakers.py          # Standalone resolver (TODO — stub)
├── annotate/            # Linguistic annotation (planned — deferred)
│   └── (post-processing pass after core extraction is complete)
├── pipeline/            # Orchestrator scripts
│   └── run_pipeline.py
├── tests/               # Verification scripts (methodology evidence)
│   ├── test_an_legislature_11_pdf_discovery.py
│   ├── test_an_legislature_12_14_pdf_url_pattern.py
│   ├── test_an_legislature_15_17_dyn_pagination.py
│   ├── test_pdf_url_validity.py
│   ├── test_an_session_links.py
│   ├── test_coverage_gaps.py
│   └── test_senat_pdf_discovery.py
├── data/                # Output directory
│   ├── pdf_inventory.csv             # AN URL inventory (version-controlled)
│   └── senat_inventory.csv           # Sénat URL inventory (version-controlled)
├── README.md
├── STATUS.md            # Current status: DONE vs STUB vs OPEN
├── METHODOLOGY.md       # How URL patterns were discovered
├── CITATION.cff         # Machine-readable citation
├── LICENSE              # (Placeholder — decision pending)
├── requirements.txt
└── .gitignore
```

## Quick start

```bash
# Set up environment
python -m venv venv
source venv/bin/activate    # or: venv\Scripts\activate (Windows)
pip install -r requirements.txt

# Step 1: Build the URL inventories
python inventory/build_url_inventory.py
# Output: data/pdf_inventory.csv (AN)
python inventory/build_senat_url_inventory.py
# Output: data/senat_inventory.csv (Sénat)

# Step 2: Download PDFs
python download/download_pdfs.py
# Output: data/pdfs/ (AN PDFs, gitignored)
python download/download_senat_pdfs.py
# Output: data/pdfs/ (Sénat PDFs, gitignored)

# Step 3: Extract text from PDFs (test batch first)
python extract/extract_text.py --test     # 7-PDF test batch
python extract/extract_text.py            # Full corpus (~10,000 PDFs)
# Output: data/extracted/speeches.csv

# Or run the full pipeline:
python pipeline/run_pipeline.py
```

## Current status

See **[STATUS.md](STATUS.md)** for a detailed breakdown of what is DONE, what is a STUB, and what are OPEN DESIGN QUESTIONS.

## License

**TBD** — decision pending. Likely CC-BY-4.0 for the dataset and MIT for the code. See [LICENSE](LICENSE) for the current placeholder.

## Target publication

This corpus is being prepared for submission as a dataset paper. Target venues:
*Language Resources & Evaluation*, *Scientific Data*, or similar. The key
novel contributions are dual-chamber coverage (no existing French parliamentary
corpus includes the Sénat), temporal extension through December 2025 (ParisParl
and ParlaMint-FR freeze at 2019), and a flat CSV/Parquet format optimised for
computational social science workflows.

## Citation

Shubhanjay Varma. *French Parliamentary Corpus 2000–2025*. University of Manchester.

```bibtex
@misc{varma_french_parliamentary_corpus,
    author = {Shubhanjay Varma},
    title = {French Parliamentary Corpus 2000--2025},
    institution = {University of Manchester},
    year = {2026},
    howpublished = {GitHub: https://github.com/Water1ock/french-parliamentary-corpus}
}
```

## Data sources

| URL pattern | Coverage | Licence |
|-------------|----------|---------|
| `archives.assemblee-nationale.fr/11/cri/{session}/{nnn}.pdf` | Legislature XI only (1997–2002) | Etalab Open Licence 2.0 (confirmed at [data.assemblee-nationale.fr/licence-ouverte-open-licence](https://data.assemblee-nationale.fr/licence-ouverte-open-licence)) |
| `www.assemblee-nationale.fr/{leg}/pdf/cri/{session}/{date}.pdf` | Legislatures XII–XIV (2002–2017) | Etalab Open Licence 2.0 |
| `www.assemblee-nationale.fr/dyn/{leg}/comptes-rendus/` | Legislatures XV–XVII (2017–2026) | Etalab Open Licence 2.0 |
| `www.senat.fr/seances/s{YYYYMM}/s{YYYYMMDD}/s{YYYYMMDD}.pdf` | Sénat 2008–2025 (PDF era) | Etalab Open Licence 2.0 (data.senat.fr) |
| `www.senat.fr/seances/s{YYYYMM}/s{YYYYMMDD}/st{YYYYMMDD}000.html` | Sénat 2003–2007 (HTML era) | Etalab Open Licence 2.0 (data.senat.fr) |

**Licence reference:** The Etalab Open Licence 2.0 (Licence Ouverte 2.0) is stated on the
Assemblée nationale's data portal at [data.assemblee-nationale.fr/licence-ouverte-open-licence](https://data.assemblee-nationale.fr/licence-ouverte-open-licence),
and applies to the official open data published by the Assemblée nationale.
The archives subdomain content falls under the same licence as it is published
by the same institution. Sénat licence is pending verification.
