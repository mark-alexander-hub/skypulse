"""Cached data loading for the Streamlit app."""

from pathlib import Path

import pandas as pd
import streamlit as st

from config import WEEKDAY_ORDER

DATA_FILE = Path("data/unified_flights.csv")


@st.cache_data  # cache so CSV is read once, survives Streamlit reruns
def load_data() -> pd.DataFrame:
    """Load the unified flight delay dataset."""
    if not DATA_FILE.exists():
        st.error(
            f"Data file not found: `{DATA_FILE}`\n\n"
            "Run the data pipeline first:\n"
            "```\npython -m data_pipeline.download_india\n"
            "python -m data_pipeline.download_us\n"
            "python -m data_pipeline.merge\n```"
        )
        st.stop()

    df = pd.read_csv(DATA_FILE, low_memory=False)

    # Coerce types
    df["Weekday"] = pd.Categorical(
        df["Weekday"], categories=WEEKDAY_ORDER, ordered=True
    )
    df["Month"] = df["Month"].astype(int)
    df["Hour"] = df["Hour"].astype(int)

    return df
