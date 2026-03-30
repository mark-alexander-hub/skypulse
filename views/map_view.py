"""Map page — interactive choropleth of airport delays using Folium."""

import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from config import INDIA_MAP_CENTER, US_MAP_CENTER, WORLD_MAP_CENTER
from utils.filters import airline_filter, month_filter


def render(df: pd.DataFrame):
    st.header("Flight Origin Airport — Delay Hours & Cost")

    col_map, col_filters = st.columns([3, 1])

    with col_filters:
        selected_airlines = airline_filter(df, key="map_airline")
        selected_months = month_filter(df, key="map_month")

    # Apply filters
    subset = df[
        (df["AIRLINE"].isin(selected_airlines)) &
        (df["Month"].isin(selected_months))
    ]

    if len(subset) == 0:
        st.info("No data for the selected filters.")
        return

    # Aggregate to airport level (same logic as R app's server.R lines 7-14)
    subset = subset.copy()
    subset["Cost_of_Delay"] = (
        subset["Direct_Aircraft_Operating_Cost_per_min"] * subset["Sum_Delay_Min"]
    )
    subset["Delay_Hours"] = subset["Sum_Delay_Min"] / 60

    agg = (
        subset.groupby(
            ["AIRPORT", "LATITUDE", "LONGITUDE", "STATE", "CITY", "ORIGIN", "COUNTRY", "CURRENCY"],
            observed=True,
        )
        .agg(
            mean_delay_hour=("Delay_Hours", "mean"),
            mean_cost=("Cost_of_Delay", "mean"),
        )
        .round(2)
        .reset_index()
    )

    with col_map:
        _render_map(agg)


def _render_map(agg: pd.DataFrame):
    """Render Folium map with circle markers for each airport."""
    # Decide map center based on which countries are present
    countries = agg["COUNTRY"].unique()
    if len(countries) == 1 and countries[0] == "US":
        center, zoom = US_MAP_CENTER, 4
    elif len(countries) == 1 and countries[0] == "India":
        center, zoom = INDIA_MAP_CENTER, 5
    else:
        center, zoom = WORLD_MAP_CENTER, 2

    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="CartoDB positron",
    )

    # Color scale based on mean delay hours
    if len(agg) == 0:
        st_folium(m, width=800, height=500)
        return

    vmin = agg["mean_delay_hour"].min()
    vmax = max(agg["mean_delay_hour"].max(), vmin + 0.1)  # avoid zero range

    colormap = cm.LinearColormap(
        colors=["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
        vmin=vmin, vmax=vmax,
        caption="Average Delay Hours per Flight",
    )
    colormap.add_to(m)

    # Add circle markers
    for _, row in agg.iterrows():
        symbol = "$" if row["CURRENCY"] == "USD" else "₹"
        tooltip = (
            f"<b>{row['AIRPORT']}</b><br>"
            f"State: {row['STATE']}<br>"
            f"City: {row['CITY']}<br>"
            f"IATA: {row['ORIGIN']}<br>"
            f"Avg Delay: {row['mean_delay_hour']:.2f} hrs<br>"
            f"Avg Cost: {symbol}{row['mean_cost']:,.2f}"
        )
        folium.CircleMarker(
            location=(row["LATITUDE"], row["LONGITUDE"]),
            radius=8,
            color=None,
            fill=True,
            fill_color=colormap(row["mean_delay_hour"]),
            fill_opacity=0.7,
            tooltip=tooltip,
        ).add_to(m)

    st_folium(m, width=800, height=500)
