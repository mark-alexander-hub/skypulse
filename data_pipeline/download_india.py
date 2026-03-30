"""Download and prepare Indian domestic flight delay data.

DATA CALIBRATION NOTE
=====================
This module generates flight-level delay data that is **statistically calibrated
to real DGCA (Directorate General of Civil Aviation) on-time performance rates**.

The primary data source is the aggregated daily OTP CSV maintained at:
  https://github.com/Vonter/india-aviation-traffic

For each day and airline where we have a real OTP percentage, we generate a
realistic number of flights (proportional to market share) and use the OTP rate
to decide which flights are delayed.  Delay minutes follow an exponential
distribution (mean ~35 min) and are split across the five BTS-style delay
categories with proportions typical of Indian aviation.

Data source priority (tried in order):
1. DGCA daily OTP CSV from GitHub
2. Local CSV fallback — user places files in data/raw/india/
3. Kaggle dataset — requires kaggle API key in ~/.kaggle/kaggle.json
4. Pure synthetic — generated sample data so the dashboard works out of the box
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd

from config import CARRIER_MAP_INDIA, INDIA_COST_PER_MIN
from data_pipeline.schema import COLUMNS, DELAY_REASON_COLS, validate

RAW_DIR = Path("data/raw/india")
OUTPUT = Path("data/india_flights.csv")

# DGCA aggregated daily OTP CSV (GitHub mirror)
DGCA_DAILY_URL = (
    "https://raw.githubusercontent.com/Vonter/india-aviation-traffic"
    "/main/aggregated/daily.csv"
)

# Kaggle dataset to try (popular Indian flight delay dataset)
KAGGLE_DATASET = "ulrikthygepedersen/airlines-delay"
KAGGLE_ALT = "imsparsh/indian-flight-dataset"

# Real Indian airport IATA codes used for synthetic generation
INDIAN_AIRPORTS = [
    "DEL", "BOM", "BLR", "MAA", "CCU", "HYD", "COK", "GOI", "PNQ", "AMD",
    "JAI", "LKO", "PAT", "GAU", "SXR", "IXB", "VNS", "NAG", "IDR", "TRV",
]

# Airline names as they appear in the DGCA OTP dataset → canonical name
# The CSV columns are like "Air India OTP (%)", so we strip " OTP (%)" to get
# the airline key.
DGCA_AIRLINE_MAP = {
    "Air Asia":     "AirAsia India",
    "Air India":    "Air India",
    "Akasa Air":    "Akasa Air",
    "Alliance Air": "Alliance Air",
    "GoAir":        "Go First",
    "Indigo":       "IndiGo",
    "Spicejet":     "SpiceJet",
    "Vistara":      "Vistara",
}

# Approximate daily flight counts per airline (reflects market share)
AIRLINE_DAILY_FLIGHTS = {
    "IndiGo":       350,   # ~30% market share → most flights
    "Air India":    200,   # ~18%
    "SpiceJet":     140,   # ~12%
    "Vistara":      130,   # ~11%
    "AirAsia India": 80,   # ~7%
    "Akasa Air":     70,   # ~6%
    "Go First":      60,   # ~5%
    "Alliance Air":  40,   # ~3%
}

# Delay category proportions for India
DELAY_PROPORTIONS = {
    "CARRIER_DELAY":        0.35,
    "LATE_AIRCRAFT_DELAY":  0.25,
    "NAS_DELAY":            0.20,
    "WEATHER_DELAY":        0.15,
    "SECURITY_DELAY":       0.05,
}

# Peak-hour departure distribution (weights for hours 0-23)
# Peaks at 6-9 AM and 5-9 PM
_HOUR_WEIGHTS = np.zeros(24)
_HOUR_WEIGHTS[5]  = 3
_HOUR_WEIGHTS[6]  = 8
_HOUR_WEIGHTS[7]  = 10
_HOUR_WEIGHTS[8]  = 10
_HOUR_WEIGHTS[9]  = 8
_HOUR_WEIGHTS[10] = 6
_HOUR_WEIGHTS[11] = 5
_HOUR_WEIGHTS[12] = 5
_HOUR_WEIGHTS[13] = 5
_HOUR_WEIGHTS[14] = 5
_HOUR_WEIGHTS[15] = 6
_HOUR_WEIGHTS[16] = 7
_HOUR_WEIGHTS[17] = 9
_HOUR_WEIGHTS[18] = 10
_HOUR_WEIGHTS[19] = 10
_HOUR_WEIGHTS[20] = 8
_HOUR_WEIGHTS[21] = 6
_HOUR_WEIGHTS[22] = 3
_HOUR_WEIGHTS[23] = 1
HOUR_PROBS = _HOUR_WEIGHTS / _HOUR_WEIGHTS.sum()

# Max rows for the final delayed-flights output
MAX_ROWS = 120_000


# ---------------------------------------------------------------------------
# Airport coordinates
# ---------------------------------------------------------------------------

def get_india_airport_coordinates() -> pd.DataFrame:
    """Download Indian airport coordinates from OpenFlights."""
    url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
    cols = [
        "airport_id", "name", "city", "country", "iata", "icao",
        "latitude", "longitude", "altitude", "timezone", "dst",
        "tz_database", "type", "source",
    ]
    df = pd.read_csv(url, header=None, names=cols)
    india = df[(df["country"] == "India") & (df["iata"] != "\\N")].copy()
    india = india[["iata", "name", "city", "latitude", "longitude"]].rename(columns={
        "iata": "ORIGIN", "name": "AIRPORT", "city": "CITY",
        "latitude": "LATITUDE", "longitude": "LONGITUDE",
    })
    india = india.drop_duplicates(subset="ORIGIN", keep="first")
    print(f"  Loaded {len(india)} Indian airports.")
    return india


# ---------------------------------------------------------------------------
# DGCA OTP-calibrated data generation
# ---------------------------------------------------------------------------

def _download_dgca_otp() -> pd.DataFrame | None:
    """Download the DGCA daily OTP CSV from GitHub. Returns DataFrame or None."""
    try:
        print(f"  Downloading DGCA daily OTP data from GitHub...")
        df = pd.read_csv(DGCA_DAILY_URL)
        print(f"  DGCA CSV loaded: {len(df)} rows, columns: {list(df.columns)[:8]}...")
        return df
    except Exception as e:
        print(f"  DGCA download failed: {e}")
        return None


def _parse_dgca_otp(dgca: pd.DataFrame) -> pd.DataFrame:
    """Parse the DGCA daily CSV into a tidy (date, airline, otp_pct) frame.

    The CSV has a 'Date' column and columns like 'Air India OTP (%)'.
    """
    # Identify OTP columns — format: "On Time Performance (Air India)" or "Air India OTP (%)"
    otp_cols = [c for c in dgca.columns
                if "on time performance" in c.lower() or ("otp" in c.upper() and "%" in c)]
    if not otp_cols:
        raise ValueError("No OTP columns found in DGCA CSV")

    dgca["Date"] = pd.to_datetime(dgca.iloc[:, 0], errors="coerce")
    dgca = dgca.dropna(subset=["Date"])

    records = []
    for col in otp_cols:
        # Extract airline name from column like "On Time Performance (Air India)"
        # or "Air India OTP (%)"
        import re
        match = re.search(r'\(([^)]+)\)', col)
        if match:
            airline_key = match.group(1).strip()
        else:
            airline_key = col.replace("OTP (%)", "").replace("OTP(%)", "").replace("On Time Performance", "").strip()
        canonical = DGCA_AIRLINE_MAP.get(airline_key)
        if canonical is None:
            # Try case-insensitive match
            for k, v in DGCA_AIRLINE_MAP.items():
                if k.lower() == airline_key.lower():
                    canonical = v
                    break
        if canonical is None:
            continue  # unknown airline, skip

        temp = dgca[["Date", col]].copy()
        temp.columns = ["date", "otp_pct"]
        # Strip "%" from values like "99.8%" before converting
        temp["otp_pct"] = temp["otp_pct"].astype(str).str.replace("%", "", regex=False)
        temp["otp_pct"] = pd.to_numeric(temp["otp_pct"], errors="coerce")
        temp = temp.dropna(subset=["otp_pct"])
        temp["airline"] = canonical
        records.append(temp)

    if not records:
        raise ValueError("Could not parse any airline OTP data from DGCA CSV")

    result = pd.concat(records, ignore_index=True)
    print(f"  Parsed OTP data: {len(result)} airline-day records, "
          f"{result['airline'].nunique()} airlines, "
          f"date range {result['date'].min().date()} to {result['date'].max().date()}")
    return result


def generate_dgca_calibrated_data(dgca_otp: pd.DataFrame) -> pd.DataFrame:
    """Generate flight-level data calibrated to real DGCA OTP rates.

    Parameters
    ----------
    dgca_otp : DataFrame with columns [date, airline, otp_pct]
    """
    rng = np.random.default_rng(42)

    all_rows = []

    for (date, airline), grp in dgca_otp.groupby(["date", "airline"]):
        otp_pct = grp["otp_pct"].iloc[0]
        if pd.isna(otp_pct) or otp_pct <= 0:
            continue

        delay_rate = max(0.0, min(1.0, 1.0 - otp_pct / 100.0))

        # Number of flights for this airline on this day
        base_flights = AIRLINE_DAILY_FLIGHTS.get(airline, 50)
        # Add some daily variance (+/- 20%)
        n_flights = int(base_flights * rng.uniform(0.8, 1.2))

        # Determine which flights are delayed
        n_delayed = int(round(n_flights * delay_rate))
        if n_delayed == 0:
            continue

        # Generate delay minutes using exponential distribution (mean ~35 min)
        delays = rng.exponential(scale=35.0, size=n_delayed)
        # Minimum delay is 1 minute (these are delayed flights)
        delays = np.maximum(delays, 1.0).round(1)

        # Split delays across 5 categories using Dirichlet
        proportions = np.array([
            DELAY_PROPORTIONS[c] for c in DELAY_REASON_COLS
        ])
        noise = rng.dirichlet(proportions * 10, size=n_delayed)

        # Departure hours with realistic peak distribution
        hours = rng.choice(24, size=n_delayed, p=HOUR_PROBS)

        # Origin airports (weighted by traffic — DEL/BOM/BLR get more)
        airport_weights = np.array([
            15, 14, 10, 8, 6, 7, 4, 3, 3, 3,
            2, 2, 2, 1, 1, 1, 1, 1, 1, 1,
        ], dtype=float)
        airport_weights /= airport_weights.sum()
        origins = rng.choice(INDIAN_AIRPORTS, size=n_delayed, p=airport_weights)

        # Flight numbers
        fl_nums = rng.integers(100, 9999, size=n_delayed).astype(str)

        date_str = date.strftime("%Y-%m-%d")
        weekday = date.strftime("%A")
        month = date.month

        batch = pd.DataFrame({
            "AIRLINE": airline,
            "ORIGIN": origins,
            "FL_DATE": date_str,
            "Date": date_str,
            "Month": month,
            "Weekday": weekday,
            "Hour": hours,
            "OP_CARRIER_FL_NUM": fl_nums,
            "ARR_DELAY": delays,
        })

        # Assign delay reasons
        for i, col in enumerate(DELAY_REASON_COLS):
            batch[col] = (delays * noise[:, i]).round(1)

        batch["Sum_Delay_Min"] = batch[DELAY_REASON_COLS].sum(axis=1).round(1)
        batch["Direct_Aircraft_Operating_Cost_per_min"] = INDIA_COST_PER_MIN
        batch["COUNTRY"] = "India"
        batch["CURRENCY"] = "INR"
        batch["STATE"] = ""
        batch["CITY"] = ""

        all_rows.append(batch)

    if not all_rows:
        raise ValueError("No delayed flights generated from DGCA OTP data")

    df = pd.concat(all_rows, ignore_index=True)
    print(f"  Generated {len(df):,} delayed flights from DGCA OTP data.")

    # Cap at MAX_ROWS to keep file size manageable
    if len(df) > MAX_ROWS:
        print(f"  Sampling down to {MAX_ROWS:,} rows...")
        df = df.sample(n=MAX_ROWS, random_state=42).reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Fallback: Kaggle download
# ---------------------------------------------------------------------------

def try_kaggle_download() -> Path | None:
    """Attempt to download from Kaggle. Returns path to CSV or None."""
    try:
        import kaggle  # noqa: F401
    except (ImportError, OSError):
        print("  Kaggle not available (no kaggle package or API key).")
        return None

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for dataset in [KAGGLE_DATASET, KAGGLE_ALT]:
        try:
            print(f"  Trying Kaggle dataset: {dataset}...")
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()
            api.dataset_download_files(dataset, path=str(RAW_DIR), unzip=True)

            # Find the downloaded CSV
            csvs = list(RAW_DIR.glob("*.csv"))
            if csvs:
                print(f"  Downloaded: {csvs[0].name}")
                return csvs[0]
        except Exception as e:
            print(f"  Kaggle download failed for {dataset}: {e}")

    return None


# ---------------------------------------------------------------------------
# Fallback: local CSV
# ---------------------------------------------------------------------------

def find_local_csv() -> Path | None:
    """Look for manually placed CSV files in data/raw/india/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    csvs = sorted(RAW_DIR.glob("*.csv"))
    if csvs:
        print(f"  Found local file: {csvs[0].name}")
        return csvs[0]
    return None


# ---------------------------------------------------------------------------
# Fallback: pure synthetic
# ---------------------------------------------------------------------------

def generate_sample_data() -> pd.DataFrame:
    """Generate realistic sample Indian flight delay data for demo purposes.

    This creates synthetic data so the dashboard works out of the box.
    Replace with real data when available.
    """
    print("  Generating pure synthetic Indian flight delay data for demo...")
    rng = np.random.default_rng(42)
    n = 50_000

    airlines = ["IndiGo", "Air India", "SpiceJet", "Vistara",
                "AirAsia India", "Akasa Air", "Go First"]
    weights = [0.30, 0.20, 0.15, 0.15, 0.08, 0.07, 0.05]

    dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    flight_dates = rng.choice(dates, size=n)

    airport_weights = np.array([
        15, 14, 10, 8, 6, 7, 4, 3, 3, 3,
        2, 2, 2, 1, 1, 1, 1, 1, 1, 1,
    ], dtype=float)
    airport_weights /= airport_weights.sum()

    df = pd.DataFrame({
        "AIRLINE": rng.choice(airlines, size=n, p=weights),
        "ORIGIN": rng.choice(INDIAN_AIRPORTS, size=n, p=airport_weights),
        "FL_DATE_dt": flight_dates,
        "Hour": rng.choice(24, size=n, p=HOUR_PROBS),
        "OP_CARRIER_FL_NUM": rng.integers(100, 9999, size=n).astype(str),
        "ARR_DELAY": np.maximum(rng.exponential(scale=35, size=n), 1.0).round(1),
    })

    # Distribute delay across reasons with realistic proportions
    proportions = np.array([
        DELAY_PROPORTIONS[c] for c in DELAY_REASON_COLS
    ])
    noise = rng.dirichlet(proportions * 10, size=n)

    for i, col in enumerate(DELAY_REASON_COLS):
        df[col] = (df["ARR_DELAY"].values * noise[:, i]).round(1)

    df["Sum_Delay_Min"] = df[DELAY_REASON_COLS].sum(axis=1).round(1)

    # Date columns
    df["FL_DATE"] = df["FL_DATE_dt"].dt.strftime("%Y-%m-%d")
    df["Date"] = df["FL_DATE"]
    df["Month"] = df["FL_DATE_dt"].dt.month
    df["Weekday"] = df["FL_DATE_dt"].dt.day_name()

    df["Direct_Aircraft_Operating_Cost_per_min"] = INDIA_COST_PER_MIN
    df["STATE"] = ""
    df["CITY"] = ""
    df["COUNTRY"] = "India"
    df["CURRENCY"] = "INR"

    df = df.drop(columns=["FL_DATE_dt"])
    return df


# ---------------------------------------------------------------------------
# Normalize real CSVs placed in data/raw/india/
# ---------------------------------------------------------------------------

def normalize_indian_data(raw: pd.DataFrame) -> pd.DataFrame:
    """Transform raw Indian CSV data to unified schema.

    Handles various column naming conventions found in Kaggle datasets.
    """
    # Standardize column names — common variants in Indian datasets
    rename_map = {}
    lower_cols = {c.lower().strip(): c for c in raw.columns}

    for target, variants in {
        "AIRLINE": ["airline", "carrier", "airline_name", "op_carrier"],
        "ORIGIN": ["origin", "source", "departure", "dep_airport", "source_city_code"],
        "FL_DATE": ["date", "flight_date", "fl_date", "date_of_journey"],
        "DEP_TIME": ["dep_time", "departure_time", "scheduled_departure"],
        "ARR_DELAY": ["arr_delay", "arrival_delay", "delay", "delay_minutes", "delay_min"],
    }.items():
        for v in variants:
            if v in lower_cols and target not in raw.columns:
                rename_map[lower_cols[v]] = target
                break

    if rename_map:
        raw = raw.rename(columns=rename_map)

    if "ARR_DELAY" not in raw.columns:
        print("  WARNING: No delay column found. Using sample data instead.")
        return generate_sample_data()

    df = raw.copy()

    # Parse dates
    if "FL_DATE" in df.columns:
        df["FL_DATE"] = pd.to_datetime(df["FL_DATE"], errors="coerce")
        df = df.dropna(subset=["FL_DATE"])
        df["Date"] = df["FL_DATE"].dt.strftime("%Y-%m-%d")
        df["Month"] = df["FL_DATE"].dt.month
        df["Weekday"] = df["FL_DATE"].dt.day_name()
        df["FL_DATE"] = df["Date"]

    # Hour
    if "DEP_TIME" in df.columns:
        dep = df["DEP_TIME"].astype(str).str.extract(r"(\d{1,2})")[0]
        df["Hour"] = pd.to_numeric(dep, errors="coerce").fillna(12).astype(int).clip(0, 23)
    elif "Hour" not in df.columns:
        df["Hour"] = 12

    # Filter to delayed flights
    df["ARR_DELAY"] = pd.to_numeric(df["ARR_DELAY"], errors="coerce").fillna(0)
    df = df[df["ARR_DELAY"] > 0].copy()

    # Delay reason columns
    for col in DELAY_REASON_COLS:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["Sum_Delay_Min"] = df[DELAY_REASON_COLS].sum(axis=1)
    mask = df["Sum_Delay_Min"] == 0
    df.loc[mask, "Sum_Delay_Min"] = df.loc[mask, "ARR_DELAY"]

    # Map airline names
    if "AIRLINE" in df.columns:
        inv_map = {v: v for v in CARRIER_MAP_INDIA.values()}
        inv_map.update(CARRIER_MAP_INDIA)
        df["AIRLINE"] = df["AIRLINE"].map(inv_map).fillna(df["AIRLINE"])

    # Metadata
    df["Direct_Aircraft_Operating_Cost_per_min"] = INDIA_COST_PER_MIN
    df["COUNTRY"] = "India"
    df["CURRENCY"] = "INR"

    if "OP_CARRIER_FL_NUM" not in df.columns:
        df["OP_CARRIER_FL_NUM"] = "N/A"
    if "STATE" not in df.columns:
        df["STATE"] = ""
    if "CITY" not in df.columns:
        df["CITY"] = ""

    return df


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def prepare_india_data() -> pd.DataFrame:
    """Full pipeline: find/download Indian data -> transform -> save.

    Data source priority:
    1. DGCA daily OTP CSV from GitHub (calibrated synthetic generation)
    2. Local CSV in data/raw/india/
    3. Kaggle dataset
    4. Pure synthetic sample data
    """
    print("\n=== Preparing Indian Flight Delay Data ===\n")

    airports = get_india_airport_coordinates()

    df = None

    # --- Source 1: DGCA OTP-calibrated generation ---
    dgca_raw = _download_dgca_otp()
    if dgca_raw is not None:
        try:
            dgca_otp = _parse_dgca_otp(dgca_raw)
            df = generate_dgca_calibrated_data(dgca_otp)
            print("  [Source: DGCA OTP-calibrated generation]")
        except Exception as e:
            print(f"  DGCA OTP parsing/generation failed: {e}")
            df = None

    # --- Source 2: Local CSV ---
    if df is None:
        csv_path = find_local_csv()
        if csv_path is not None:
            print(f"  Reading {csv_path.name}...")
            raw = pd.read_csv(csv_path, low_memory=False)
            df = normalize_indian_data(raw)
            print("  [Source: local CSV]")

    # --- Source 3: Kaggle ---
    if df is None:
        csv_path = try_kaggle_download()
        if csv_path is not None:
            print(f"  Reading {csv_path.name}...")
            raw = pd.read_csv(csv_path, low_memory=False)
            df = normalize_indian_data(raw)
            print("  [Source: Kaggle]")

    # --- Source 4: Pure synthetic fallback ---
    if df is None:
        print("  No Indian data source found — falling back to pure synthetic.")
        df = generate_sample_data()
        print("  [Source: pure synthetic]")

    print(f"  Delayed flights: {len(df):,}")

    # Join airport coordinates
    print("  Joining airport coordinates...")
    df = df.merge(
        airports[["ORIGIN", "AIRPORT", "LATITUDE", "LONGITUDE"]],
        on="ORIGIN", how="left", suffixes=("_old", ""),
    )

    # Fill city from airports if missing
    city_map = airports.set_index("ORIGIN")["CITY"].to_dict()
    mask = (df["CITY"] == "") | df["CITY"].isna()
    df.loc[mask, "CITY"] = df.loc[mask, "ORIGIN"].map(city_map)

    # Drop flights with no coordinates
    before = len(df)
    df = df.dropna(subset=["LATITUDE"])
    if before - len(df) > 0:
        print(f"  Dropped {before - len(df)} flights with unknown airports.")

    # Select final columns
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS].copy()

    df = validate(df)

    # Save
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"\nSaved {len(df):,} rows -> {OUTPUT}")
    print(f"Airlines: {', '.join(sorted(df['AIRLINE'].unique()))}")

    return df


if __name__ == "__main__":
    prepare_india_data()
