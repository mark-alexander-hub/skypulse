"""Shared sidebar filter widgets used across pages."""

import pandas as pd
import streamlit as st


def country_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Render country multiselect in sidebar; return filtered df."""
    countries = sorted(df["COUNTRY"].unique())
    selected = st.sidebar.multiselect(
        "Country", countries, default=countries, key="filter_country"
    )
    if not selected:
        st.warning("Select at least one country.")
        st.stop()
    return df[df["COUNTRY"].isin(selected)]


def airline_filter(
    df: pd.DataFrame, key: str, multi: bool = True, default: str | None = None
) -> list[str] | str:
    """Render airline selector. Returns selected value(s)."""
    airlines = sorted(df["AIRLINE"].unique())

    if multi:
        selected = st.multiselect(
            "Select Airlines", airlines,
            default=[default] if default and default in airlines else airlines[:1],
            key=key,
        )
    else:
        idx = airlines.index(default) if default and default in airlines else 0
        selected = st.selectbox("Select Airline", airlines, index=idx, key=key)

    return selected


def airport_filter(df: pd.DataFrame, key: str) -> str:
    """Render airport selectbox. Returns selected IATA code."""
    airports = sorted(df["ORIGIN"].unique())
    return st.selectbox("Select Origin Airport", airports, key=key)


def month_filter(df: pd.DataFrame, key: str) -> list[int]:
    """Render month multiselect. Returns list of selected months."""
    months = sorted(df["Month"].unique())
    return st.multiselect(
        "Select Month", months, default=[months[0]], key=key
    )
