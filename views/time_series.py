"""Time Series page — daily delay frequency and cost trends."""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.filters import airline_filter


def render(df: pd.DataFrame):
    st.header("Time Series")

    col_chart, col_filter = st.columns([3, 1])

    with col_filter:
        selected = airline_filter(df, key="ts_airline")

    if not selected:
        st.info("Select at least one airline.")
        return

    subset = df[df["AIRLINE"].isin(selected)].copy()
    subset["date"] = pd.to_datetime(subset["FL_DATE"])

    # --- Chart 1: Daily delay frequency ---
    with col_chart:
        freq = (
            subset.groupby(["date", "AIRLINE"])
            .size()
            .reset_index(name="Num_Delays")
        )
        fig1 = px.line(
            freq, x="date", y="Num_Delays", color="AIRLINE",
            title="Frequency of Delays — Daily Trend",
            labels={"date": "Date", "Num_Delays": "Number of Delayed Flights"},
        )
        st.plotly_chart(fig1, use_container_width=True)

    # --- Chart 2: Daily cost of delays ---
    subset["cost"] = (
        subset["Sum_Delay_Min"] * subset["Direct_Aircraft_Operating_Cost_per_min"]
    )

    # Group by date and country so we don't mix currencies
    cost_agg = (
        subset.groupby(["date", "COUNTRY", "CURRENCY"])["cost"]
        .sum()
        .reset_index()
    )

    for country in sorted(cost_agg["COUNTRY"].unique()):
        c_data = cost_agg[cost_agg["COUNTRY"] == country]
        currency = c_data["CURRENCY"].iloc[0]
        symbol = "$" if currency == "USD" else "₹"

        fig2 = px.line(
            c_data, x="date", y="cost",
            title=f"Cost of Delays — {country} ({symbol})",
            labels={"date": "Date", "cost": f"Total Cost ({currency})"},
        )
        fig2.update_traces(line_color="#69b3a2")
        st.plotly_chart(fig2, use_container_width=True)

    st.caption(
        "Cost calculated using estimated Direct Aircraft Operating Cost: "
        "$74.2/min (US), ₹45/min (India)"
    )
