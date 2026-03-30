"""Box Plots page — delay hour distributions by month, weekday, hour."""

import pandas as pd
import plotly.express as px
import streamlit as st

from config import WEEKDAY_ORDER
from utils.filters import airline_filter


def render(df: pd.DataFrame):
    st.header("Delay Hours — Box Plots")

    # Pre-compute Delay_Hours column
    plot_df = df.copy()
    plot_df["Delay_Hours"] = (plot_df["Sum_Delay_Min"] / 60).round(2)

    # --- Box Plot 1: By Month ---
    col1, col1f = st.columns([3, 1])
    with col1f:
        air1 = airline_filter(plot_df, key="box_month", multi=False)
    with col1:
        sub1 = plot_df[plot_df["AIRLINE"] == air1] if isinstance(air1, str) else plot_df
        fig1 = px.box(
            sub1, x="Month", y="Delay_Hours",
            title="Delay Hours by Month",
            labels={"Delay_Hours": "Delay (Hours)", "Month": "Month"},
        )
        fig1.update_layout(xaxis=dict(dtick=1))
        st.plotly_chart(fig1, use_container_width=True)

    st.markdown("---")

    # --- Box Plot 2: By Weekday ---
    col2, col2f = st.columns([3, 1])
    with col2f:
        air2 = airline_filter(plot_df, key="box_week", multi=False)
    with col2:
        sub2 = plot_df[plot_df["AIRLINE"] == air2] if isinstance(air2, str) else plot_df
        # Sort weekdays properly
        sub2 = sub2.copy()
        sub2["Weekday"] = pd.Categorical(
            sub2["Weekday"], categories=WEEKDAY_ORDER, ordered=True
        )
        fig2 = px.box(
            sub2.sort_values("Weekday"), x="Weekday", y="Delay_Hours",
            title="Delay Hours by Weekday",
            labels={"Delay_Hours": "Delay (Hours)"},
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # --- Box Plot 3: By Hour ---
    col3, col3f = st.columns([3, 1])
    with col3f:
        air3 = airline_filter(plot_df, key="box_hour", multi=False)
    with col3:
        sub3 = plot_df[plot_df["AIRLINE"] == air3] if isinstance(air3, str) else plot_df
        fig3 = px.box(
            sub3, x="Hour", y="Delay_Hours",
            title="Delay Hours by Hour of Day",
            labels={"Delay_Hours": "Delay (Hours)", "Hour": "Hour"},
        )
        fig3.update_layout(xaxis=dict(dtick=1))
        st.plotly_chart(fig3, use_container_width=True)
