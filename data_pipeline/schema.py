"""Unified data schema for US + India flight delay data."""

import pandas as pd

# The 23 columns every row must have after processing
COLUMNS = [
    "COUNTRY",
    "CURRENCY",
    "AIRLINE",
    "ORIGIN",
    "AIRPORT",
    "LATITUDE",
    "LONGITUDE",
    "STATE",
    "CITY",
    "OP_CARRIER_FL_NUM",
    "FL_DATE",
    "Date",
    "Month",
    "Weekday",
    "Hour",
    "ARR_DELAY",
    "Sum_Delay_Min",
    "Direct_Aircraft_Operating_Cost_per_min",
    "CARRIER_DELAY",
    "WEATHER_DELAY",
    "NAS_DELAY",
    "SECURITY_DELAY",
    "LATE_AIRCRAFT_DELAY",
]

DELAY_REASON_COLS = [
    "CARRIER_DELAY",
    "WEATHER_DELAY",
    "NAS_DELAY",
    "SECURITY_DELAY",
    "LATE_AIRCRAFT_DELAY",
]

WEEKDAY_ORDER = [
    "Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday",
]


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Check that df has the required columns and coerce types."""
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # Coerce Weekday to ordered categorical
    df["Weekday"] = pd.Categorical(
        df["Weekday"], categories=WEEKDAY_ORDER, ordered=True
    )
    df["Month"] = df["Month"].astype(int)
    df["Hour"] = df["Hour"].astype(int)

    return df
