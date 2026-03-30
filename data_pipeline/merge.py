"""Merge US and India flight delay data into a single unified CSV."""

from pathlib import Path

import pandas as pd

from data_pipeline.schema import validate

US_FILE = Path("data/us_flights.csv")
INDIA_FILE = Path("data/india_flights.csv")
OUTPUT = Path("data/unified_flights.csv")


def merge_datasets() -> pd.DataFrame:
    """Read country CSVs, concatenate, validate, and save unified file."""
    print("\n=== Merging Flight Delay Datasets ===\n")

    frames = []

    if US_FILE.exists():
        us = pd.read_csv(US_FILE, low_memory=False)
        print(f"US data:    {len(us):>10,} rows")
        frames.append(us)
    else:
        print(f"WARNING: {US_FILE} not found. Run download_us.py first.")

    if INDIA_FILE.exists():
        india = pd.read_csv(INDIA_FILE, low_memory=False)
        print(f"India data: {len(india):>10,} rows")
        frames.append(india)
    else:
        print(f"WARNING: {INDIA_FILE} not found. Run download_india.py first.")

    if not frames:
        raise RuntimeError("No data files found. Run the download scripts first.")

    merged = pd.concat(frames, ignore_index=True)
    merged = validate(merged)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT, index=False)

    print(f"\n{'='*50}")
    print(f"Unified dataset: {len(merged):,} rows → {OUTPUT}")
    print(f"Countries: {', '.join(sorted(merged['COUNTRY'].unique()))}")
    print(f"Airlines:  {merged['AIRLINE'].nunique()}")
    print(f"Airports:  {merged['ORIGIN'].nunique()}")
    if "FL_DATE" in merged.columns:
        print(f"Dates:     {merged['FL_DATE'].min()} → {merged['FL_DATE'].max()}")
    print(f"File size: {OUTPUT.stat().st_size / 1024**2:.1f} MB")

    return merged


if __name__ == "__main__":
    merge_datasets()
