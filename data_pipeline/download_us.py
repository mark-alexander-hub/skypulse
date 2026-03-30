"""Download and prepare US flight delay data from BTS."""

import io
import os
import zipfile
from pathlib import Path

import pandas as pd
import requests

from config import CARRIER_MAP_US, US_COST_PER_MIN
from data_pipeline.schema import DELAY_REASON_COLS, validate

# BTS URL pattern for On-Time Reporting data
BTS_URL = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{}_{}.zip"
)

RAW_DIR = Path("data/raw")
OUTPUT = Path("data/us_flights.csv")


def get_airport_coordinates() -> pd.DataFrame:
    """Download US airport coordinates from OpenFlights."""
    url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
    print("Downloading airport coordinates...")

    cols = [
        "airport_id", "name", "city", "country", "iata", "icao",
        "latitude", "longitude", "altitude", "timezone", "dst",
        "tz_database", "type", "source",
    ]
    df = pd.read_csv(url, header=None, names=cols)

    # Filter to US airports with valid IATA codes
    us = df[(df["country"] == "United States") & (df["iata"] != "\\N")].copy()
    us = us[["iata", "name", "city", "latitude", "longitude"]].rename(columns={
        "iata": "ORIGIN", "name": "AIRPORT", "city": "CITY_COORDS",
        "latitude": "LATITUDE", "longitude": "LONGITUDE",
    })
    # Keep first occurrence per IATA code
    us = us.drop_duplicates(subset="ORIGIN", keep="first")
    print(f"  Loaded {len(us)} US airports.")
    return us


def download_month(year: int, month: int) -> pd.DataFrame | None:
    """Download one month of BTS on-time data, return as DataFrame."""
    csv_path = RAW_DIR / f"ontime_{year}_{month}.csv"

    if csv_path.exists():
        print(f"  {year}-{month:02d}: cached, reading...")
        return pd.read_csv(csv_path, low_memory=False)

    url = BTS_URL.format(year, month)
    print(f"  {year}-{month:02d}: downloading...")

    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Failed: {e}")
        return None

    # Extract CSV from the zip (it's in-memory, no temp file needed)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        zf.extract(csv_name, RAW_DIR)
        extracted = RAW_DIR / csv_name
        extracted.rename(csv_path)

    return pd.read_csv(csv_path, low_memory=False)


def prepare_us_data(year: int = 2024, max_rows: int = 500_000) -> pd.DataFrame:
    """Full pipeline: download BTS data → transform → return unified schema."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    airports = get_airport_coordinates()

    # --- Download all months ---
    print(f"\nDownloading BTS data for {year}...")
    frames = []
    for month in range(1, 13):
        df = download_month(year, month)
        if df is not None:
            frames.append(df)

    if not frames:
        raise RuntimeError("No BTS data downloaded. Check connection / year.")

    raw = pd.concat(frames, ignore_index=True)
    print(f"\nTotal raw records: {len(raw):,}")

    # --- Rename BTS CamelCase columns to our ALL_CAPS convention ---
    # BTS changed column naming over time; map both old and new formats
    col_rename = {
        # Current BTS CamelCase format (2024+)
        "IATA_CODE_Reporting_Airline": "OP_UNIQUE_CARRIER",
        "Reporting_Airline": "REPORTING_AIRLINE",
        "Flight_Number_Reporting_Airline": "OP_CARRIER_FL_NUM",
        "Origin": "ORIGIN",
        "OriginCityName": "ORIGIN_CITY_NAME",
        "OriginState": "ORIGIN_STATE_ABR",
        "FlightDate": "FL_DATE",
        "DepTime": "DEP_TIME",
        "ArrDelay": "ARR_DELAY",
        "CarrierDelay": "CARRIER_DELAY",
        "WeatherDelay": "WEATHER_DELAY",
        "NASDelay": "NAS_DELAY",
        "SecurityDelay": "SECURITY_DELAY",
        "LateAircraftDelay": "LATE_AIRCRAFT_DELAY",
    }
    raw = raw.rename(columns={k: v for k, v in col_rename.items() if k in raw.columns})
    print(f"Columns after rename: {list(raw.columns[:10])}... ({len(raw.columns)} total)")

    # --- Filter to delayed flights with at least one reason ---
    needed = [
        "OP_UNIQUE_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN",
        "ORIGIN_CITY_NAME", "ORIGIN_STATE_ABR", "FL_DATE",
        "DEP_TIME", "ARR_DELAY",
    ] + DELAY_REASON_COLS

    # Keep only columns that exist
    available = [c for c in needed if c in raw.columns]
    raw = raw[available].copy()

    # Fill NaN delay reasons with 0
    for col in DELAY_REASON_COLS:
        if col in raw.columns:
            raw[col] = raw[col].fillna(0)

    delayed = raw[raw["ARR_DELAY"] > 0].copy()
    delayed = delayed[
        delayed[DELAY_REASON_COLS].gt(0).any(axis=1)
    ]
    print(f"Delayed flights: {len(delayed):,}")

    # --- Transform ---
    # Airline name
    delayed["AIRLINE"] = delayed["OP_UNIQUE_CARRIER"].map(CARRIER_MAP_US)
    # Keep carrier code as fallback if not in map
    delayed["AIRLINE"] = delayed["AIRLINE"].fillna(delayed["OP_UNIQUE_CARRIER"])

    # Date parts
    delayed["FL_DATE"] = pd.to_datetime(delayed["FL_DATE"])
    delayed["Date"] = delayed["FL_DATE"].dt.strftime("%Y-%m-%d")
    delayed["Month"] = delayed["FL_DATE"].dt.month
    delayed["Weekday"] = delayed["FL_DATE"].dt.day_name()
    delayed["FL_DATE"] = delayed["Date"]  # store as string

    # Hour from departure time (HHMM numeric → integer hour)
    delayed["Hour"] = (delayed["DEP_TIME"].fillna(0).astype(int) // 100).clip(0, 23)

    # Totals and cost
    delayed["Sum_Delay_Min"] = delayed[DELAY_REASON_COLS].sum(axis=1)
    delayed["Direct_Aircraft_Operating_Cost_per_min"] = US_COST_PER_MIN

    # Geography
    delayed["STATE"] = delayed["ORIGIN_STATE_ABR"]
    delayed["CITY"] = delayed["ORIGIN_CITY_NAME"].str.replace(r",.*", "", regex=True)

    # Country / currency
    delayed["COUNTRY"] = "US"
    delayed["CURRENCY"] = "USD"

    # --- Join airport coordinates ---
    print("Joining airport coordinates...")
    merged = delayed.merge(
        airports[["ORIGIN", "AIRPORT", "LATITUDE", "LONGITUDE"]],
        on="ORIGIN", how="left",
    )
    before = len(merged)
    merged = merged.dropna(subset=["LATITUDE"])
    print(f"  Dropped {before - len(merged)} flights with unknown airports.")

    # --- Select final columns ---
    from data_pipeline.schema import COLUMNS
    merged = merged[COLUMNS].copy()

    # --- Sample if needed ---
    if max_rows and len(merged) > max_rows:
        print(f"Sampling {max_rows:,} from {len(merged):,}...")
        merged = merged.sample(n=max_rows, random_state=42)

    merged = validate(merged)

    # --- Save ---
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT, index=False)
    print(f"\nSaved {len(merged):,} rows → {OUTPUT}")
    print(f"Airlines: {', '.join(sorted(merged['AIRLINE'].unique()))}")

    return merged


if __name__ == "__main__":
    prepare_us_data()
