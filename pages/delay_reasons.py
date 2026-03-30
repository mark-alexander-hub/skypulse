"""Reasons of Delay page — grouped bar charts by airline and airport."""

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DELAY_REASON_DESCRIPTIONS
from data_pipeline.schema import DELAY_REASON_COLS
from utils.filters import airline_filter, airport_filter


def render(df: pd.DataFrame):
    st.header("Reasons of Delay")

    # --- Chart 1: By Airline ---
    col_chart, col_filter = st.columns([3, 1])

    with col_filter:
        selected_airlines = airline_filter(df, key="reason_airline")

    with col_chart:
        if selected_airlines:
            subset = df[df["AIRLINE"].isin(selected_airlines)]
            fig = _reason_bar_chart(subset, "Average Delay Hours per Flight (by Airline)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least one airline.")

    st.markdown("---")

    # --- Chart 2: By Airport ---
    col_chart2, col_filter2 = st.columns([3, 1])

    with col_filter2:
        selected_airport = airport_filter(df, key="reason_airport")

    with col_chart2:
        subset2 = df[df["ORIGIN"] == selected_airport]
        if len(subset2) > 0:
            fig2 = _reason_bar_chart(subset2, f"Average Delay Hours per Flight ({selected_airport})")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No delay data for this airport.")

    # --- Delay reason descriptions ---
    st.markdown("---")
    for reason, desc in DELAY_REASON_DESCRIPTIONS.items():
        # Clean up column name for display: CARRIER_DELAY → Carrier Delay
        label = reason.replace("_", " ").title()
        st.markdown(f"**{label}**: {desc}")


def _reason_bar_chart(df: pd.DataFrame, title: str):
    """Build a grouped bar chart of avg delay hours by month and reason."""
    # Melt delay reason columns into long format (like R's gather)
    melted = df.melt(
        id_vars=["Month"],
        value_vars=DELAY_REASON_COLS,
        var_name="Reason",
        value_name="delay_min",
    )
    melted["Delay_Hours"] = melted["delay_min"] / 60

    agg = (
        melted.groupby(["Month", "Reason"], observed=False)["Delay_Hours"]
        .mean()
        .round(2)
        .reset_index()
    )

    fig = px.bar(
        agg, x="Month", y="Delay_Hours", color="Reason",
        barmode="group", title=title,
        labels={"Delay_Hours": "Avg Delay Hours", "Month": "Month"},
    )
    fig.update_layout(xaxis=dict(dtick=1))
    return fig
