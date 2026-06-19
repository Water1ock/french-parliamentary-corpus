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

## Repository structure

```
french-parliamentary-corpus/
├── inventory/           # URL discovery scripts
│   └── build_url_inventory.py   # AN PDF URL discovery (DONE)
├── download/            # PDF downloader (resume-safe)
│   └── download_pdfs.py
├── extract/             # PDF text extraction (TODO — stub)
│   └── extract_text.py
├── resolve_speakers/    # Speaker→party resolution (TODO — open design)
│   └── resolve_speakers.py
├── pipeline/            # Orchestrator scripts
│   └── run_pipeline.py
├── tests/               # Verification scripts (methodology evidence)
│   ├── test_an_legislature_11_pdf_discovery.py
│   ├── test_an_legislature_12_14_pdf_url_pattern.py
│   ├── test_an_legislature_15_17_dyn_pagination.py
│   ├── test_pdf_url_validity.py
│   ├── test_an_session_links.py
│   └── test_coverage_gaps.py
├── data/                # Output directory
│   └── pdf_inventory.csv        # URL inventory (version-controlled)
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

# Step 1: Build the URL inventory
python inventory/build_url_inventory.py
# Output: data/pdf_inventory.csv

# Step 2: Download PDFs
python download/download_pdfs.py
# Output: data/pdfs/ (gitignored)

# Or run the full pipeline:
python pipeline/run_pipeline.py
```

## Current status

See **[STATUS.md](STATUS.md)** for a detailed breakdown of what is DONE, what is a STUB, and what are OPEN DESIGN QUESTIONS.

## License

**TBD** — decision pending. Likely CC-BY-4.0 for the dataset and MIT for the code. See [LICENSE](LICENSE) for the current placeholder.

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

| Source | Coverage | Licence |
|--------|----------|---------|
| data.assemblee-nationale.fr | AN 14th–17th legislature (2012–2026) | Etalab Open Licence 2.0 |
| archives.assemblee-nationale.fr | AN 11th–13th legislature (1997–2012) | Etalab Open Licence 2.0 |
| data.senat.fr (TODO) | Sénat (pending URL discovery) | Etalab Open Licence 2.0 |
| www.senat.fr (TODO) | Sénat (pending URL discovery) | Etalab Open Licence 2.0 |
