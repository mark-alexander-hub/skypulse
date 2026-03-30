"""Data table page — interactive, sortable, searchable."""

import pandas as pd
import streamlit as st


# Columns to display (matches R app + COUNTRY)
DISPLAY_COLS = [
    "COUNTRY", "ORIGIN", "AIRLINE", "OP_CARRIER_FL_NUM", "FL_DATE",
    "ARR_DELAY", "CARRIER_DELAY", "WEATHER_DELAY", "NAS_DELAY",
    "SECURITY_DELAY", "LATE_AIRCRAFT_DELAY",
]


def render(df: pd.DataFrame):
    st.header("Cleaned Data")

    # st.dataframe gives sorting + search out of the box
    st.dataframe(
        df[DISPLAY_COLS],
        use_container_width=True,
        height=600,
    )

    st.caption(f"Showing {len(df):,} delayed flights.")
