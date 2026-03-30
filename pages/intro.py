"""Introduction page — summary stats and background."""

import pandas as pd
import streamlit as st


def render(df: pd.DataFrame):
    st.title("SkyPulse — US & India Flight Delay Analysis")

    st.markdown(
        """
        There are thousands of flight delays every day across the US and India.
        Direct Aircraft Operating Cost is **$74.2/min** (US) and **₹45/min** (India).
        Flight delays cost airlines billions every year.

        This dashboard analyzes delayed flights across major airlines using
        **Bureau of Transportation Statistics** (US) and **DGCA** (India) data.
        Use the tabs on the left to explore delay patterns by airport, airline,
        time of day, and cause.
        """
    )

    st.markdown("---")

    # Summary metric cards — one row of key stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Delayed Flights", f"{len(df):,}")
    with col2:
        st.metric("Airlines", df["AIRLINE"].nunique())
    with col3:
        st.metric("Airports", df["ORIGIN"].nunique())
    with col4:
        st.metric("Countries", df["COUNTRY"].nunique())

    # Per-country breakdown
    st.subheader("By Country")
    for country in sorted(df["COUNTRY"].unique()):
        subset = df[df["COUNTRY"] == country]
        currency = subset["CURRENCY"].iloc[0]
        symbol = "$" if currency == "USD" else "₹"
        avg_delay = subset["Sum_Delay_Min"].mean()
        avg_cost = avg_delay * subset["Direct_Aircraft_Operating_Cost_per_min"].iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(f"{country} — Flights", f"{len(subset):,}")
        with c2:
            st.metric("Airlines", subset["AIRLINE"].nunique())
        with c3:
            st.metric("Avg Delay", f"{avg_delay:.0f} min")
        with c4:
            st.metric("Avg Cost/Flight", f"{symbol}{avg_cost:,.0f}")

    st.markdown("---")

    # Date range
    st.caption(f"Date range: {df['FL_DATE'].min()} to {df['FL_DATE'].max()}")
