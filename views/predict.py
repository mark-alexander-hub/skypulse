"""Predict page — ML-powered flight delay prediction."""

from pathlib import Path

import pandas as pd
import streamlit as st

from config import WEEKDAY_ORDER


def render(df: pd.DataFrame):
    st.header("Predict Flight Delay")

    # Check if models exist
    if not Path("models/delay_classifier.pkl").exists():
        st.warning(
            "ML models not trained yet. Run:\n"
            "```\npython ml_model.py\n```"
        )
        return

    # Lazy import to avoid loading models on every page
    from ml_model import predict

    st.markdown(
        "Enter flight details to predict the likelihood and severity of delay. "
        "The model uses a **Random Forest classifier** (delay risk) and "
        "**XGBoost regressor** (expected minutes) trained on 550K+ real flight records."
    )

    st.markdown("---")

    # --- Input form ---
    col1, col2 = st.columns(2)

    with col1:
        country = st.selectbox(
            "Country",
            sorted(df["COUNTRY"].unique()),
            key="pred_country",
        )

        # Filter airlines and airports by selected country
        country_df = df[df["COUNTRY"] == country]

        airline = st.selectbox(
            "Airline",
            sorted(country_df["AIRLINE"].unique()),
            key="pred_airline",
        )

        origin = st.selectbox(
            "Departure Airport",
            sorted(country_df["ORIGIN"].unique()),
            key="pred_origin",
        )

    with col2:
        month = st.selectbox(
            "Month",
            list(range(1, 13)),
            format_func=lambda m: [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ][m - 1],
            key="pred_month",
        )

        weekday = st.selectbox(
            "Day of Week",
            WEEKDAY_ORDER,
            key="pred_weekday",
        )

        hour = st.slider(
            "Departure Hour",
            min_value=0, max_value=23, value=14,
            format="%d:00",
            key="pred_hour",
        )

    st.markdown("---")

    # --- Predict button ---
    if st.button("Predict Delay", type="primary", use_container_width=True):
        with st.spinner("Running prediction..."):
            result = predict(
                country=country,
                airline=airline,
                origin=origin,
                month=month,
                hour=hour,
                weekday=weekday,
            )

        # --- Display results ---
        prob = result["delay_probability"]
        minutes = result["expected_minutes"]
        risk = result["risk_level"]

        # Color-coded risk
        risk_colors = {"Low": "green", "Medium": "orange", "High": "red"}
        risk_color = risk_colors.get(risk, "gray")

        st.markdown("### Prediction Results")

        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("Delay Probability", f"{prob:.0%}")
        with r2:
            st.metric("Expected Delay", f"{minutes:.0f} min")
        with r3:
            st.markdown(
                f"**Risk Level**<br>"
                f"<span style='color:{risk_color}; font-size:2em; font-weight:bold;'>"
                f"{risk}</span>",
                unsafe_allow_html=True,
            )

        # Progress bar for probability
        st.progress(min(prob, 1.0))

        # Context from historical data
        st.markdown("---")
        st.markdown("#### Historical Context")

        hist = country_df[
            (country_df["AIRLINE"] == airline) &
            (country_df["Month"] == month)
        ]
        if len(hist) > 0:
            avg_delay = hist["Sum_Delay_Min"].mean()
            currency = hist["CURRENCY"].iloc[0]
            cost_per_min = hist["Direct_Aircraft_Operating_Cost_per_min"].iloc[0]
            symbol = "$" if currency == "USD" else "₹"

            h1, h2, h3 = st.columns(3)
            with h1:
                st.metric(
                    f"Avg Delay ({airline}, Month {month})",
                    f"{avg_delay:.0f} min",
                )
            with h2:
                st.metric(
                    "Avg Cost per Delayed Flight",
                    f"{symbol}{avg_delay * cost_per_min:,.0f}",
                )
            with h3:
                st.metric(
                    "Flights in Dataset",
                    f"{len(hist):,}",
                )
        else:
            st.info("No historical data for this airline/month combination.")
