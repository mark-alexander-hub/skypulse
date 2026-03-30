"""Heatmap page — delay frequency by hour and weekday."""

import pandas as pd
import plotly.express as px
import streamlit as st

from config import WEEKDAY_ORDER
from utils.filters import airline_filter, airport_filter


def render(df: pd.DataFrame):
    st.header("Delay Frequency Heatmap")

    # --- Heatmap 1: By Airline ---
    col_chart, col_filter = st.columns([3, 1])

    with col_filter:
        selected = airline_filter(df, key="heat_airline")

    with col_chart:
        if selected:
            subset = df[df["AIRLINE"].isin(selected)]
            fig = _heatmap(subset, "Delays by Hour & Weekday (Airline)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least one airline.")

    st.markdown("---")

    # --- Heatmap 2: By Airport ---
    col_chart2, col_filter2 = st.columns([3, 1])

    with col_filter2:
        selected_airport = airport_filter(df, key="heat_airport")

    with col_chart2:
        subset2 = df[df["ORIGIN"] == selected_airport]
        if len(subset2) > 0:
            fig2 = _heatmap(subset2, f"Delays by Hour & Weekday ({selected_airport})")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data for this airport.")


def _heatmap(df: pd.DataFrame, title: str):
    """Build hour × weekday heatmap of delay counts."""
    agg = (
        df.groupby(["Weekday", "Hour"], observed=True)
        .size()
        .reset_index(name="Number_Delays")
    )

    # Pivot for imshow: rows = weekday, cols = hour
    pivot = agg.pivot_table(
        index="Weekday", columns="Hour", values="Number_Delays", fill_value=0
    )

    # Ensure weekday order
    ordered = [d for d in WEEKDAY_ORDER if d in pivot.index]
    pivot = pivot.reindex(ordered)

    fig = px.imshow(
        pivot,
        title=title,
        labels=dict(x="Hour", y="Weekday", color="Number of Delays"),
        color_continuous_scale="YlOrRd",
        aspect="auto",
    )
    return fig
