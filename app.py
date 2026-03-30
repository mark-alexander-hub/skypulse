"""Flight Delay Analysis Dashboard — Streamlit entry point.

Run with:  streamlit run app.py
"""

import streamlit as st

from utils.data_loader import load_data
from utils.filters import country_filter

# --- Page config (must be first Streamlit call) ---
st.set_page_config(
    page_title="SkyPulse — Flight Delay Analysis",
    page_icon="✈️",
    layout="wide",
)

# --- Load data (cached) ---
df = load_data()

# --- Sidebar ---
st.sidebar.title("SkyPulse")

# Navigation — 7 analysis tabs + ML prediction
page = st.sidebar.radio("Navigation", [
    "Introduction",
    "Predict",
    "Map",
    "Reasons of Delay",
    "Heatmap",
    "Time Series",
    "Delay Hours Box Plots",
    "Data",
])

st.sidebar.markdown("---")

# Global country filter
filtered = country_filter(df)

# --- Page routing ---
# Import pages lazily to avoid circular imports and speed up startup
if page == "Introduction":
    from pages.intro import render
elif page == "Predict":
    from pages.predict import render
elif page == "Map":
    from pages.map_view import render
elif page == "Reasons of Delay":
    from pages.delay_reasons import render
elif page == "Heatmap":
    from pages.heatmap import render
elif page == "Time Series":
    from pages.time_series import render
elif page == "Delay Hours Box Plots":
    from pages.box_plots import render
elif page == "Data":
    from pages.data_table import render

render(filtered)
