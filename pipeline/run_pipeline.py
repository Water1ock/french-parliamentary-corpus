#!/usr/bin/env python3
"""
run_pipeline.py — Orchestrate the full corpus pipeline.

This script runs each stage of the pipeline in order, designed to be
INCREMENTAL: it only processes new sessions/discoveries since the last run.

Usage:
    python pipeline/run_pipeline.py [--step STEP]

Steps (run in order):
    1. inventory  — Discover and build URL inventory
    2. download   — Download missing PDFs
    3. extract    — Extract speech text from PDFs (TODO — stub)
    4. resolve    — Resolve speaker names and parties (TODO — stub)

If --step is provided, only that step and subsequent steps are run.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Ensure CWD is the repo root (where this script lives)
os.chdir(Path(__file__).resolve().parent.parent)


def run_step(name: str, script: str) -> None:
    """Run a single pipeline step via subprocess."""
    print(f"\n{'='*60}")
    print(f"  STEP: {name}")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, script], capture_output=False)
    if result.returncode != 0:
        print(f"❌ Step '{name}' failed (exit code {result.returncode}). Aborting.")
        sys.exit(result.returncode)
    print(f"✅ Step '{name}' complete.\n")


STEPS = [
    ("inventory", "inventory/build_url_inventory.py"),
    ("download", "download/download_pdfs.py"),
    ("extract", "extract/extract_text.py"),
    ("resolve", "resolve_speakers/resolve_speakers.py"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the corpus pipeline")
    parser.add_argument(
        "--step",
        choices=[s[0] for s in STEPS],
        default=None,
        help="Start from this step (runs it and all subsequent steps)"
    )
    args = parser.parse_args()

    start_index = 0
    if args.step:
        names = [s[0] for s in STEPS]
        start_index = names.index(args.step)
        print(f"Starting from step '{args.step}' (index {start_index})")

    for name, script in STEPS[start_index:]:
        if not Path(script).exists():
            print(f"⚠️  Script not found: {script} — skipping step '{name}'")
            continue
        run_step(name, script)

    print("✅ Pipeline complete.")


if __name__ == "__main__":
    main()
