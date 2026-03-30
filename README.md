# SkyPulse

**Interactive flight delay analysis dashboard for US and Indian domestic airlines.**

SkyPulse visualizes delay patterns across 22 airlines and 358 airports using 2024 data from the Bureau of Transportation Statistics (US) and DGCA (India). Built with Python, Streamlit, Plotly, and Folium.

![Python](https://img.shields.io/badge/Python-3.14-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.55-red)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

| Tab | Description |
|-----|-------------|
| **Introduction** | Summary stats, per-country metrics, date range |
| **Map** | Interactive Folium map with airport delay markers (US + India) |
| **Reasons of Delay** | Grouped bar charts breaking down 5 delay categories by airline and airport |
| **Heatmap** | Hour x Weekday delay frequency heatmaps |
| **Time Series** | Daily delay count and cost trends with currency-aware display |
| **Box Plots** | Delay hour distributions by month, weekday, and hour of day |
| **Data** | Searchable, sortable table of all 550K delayed flights |

**Global filters**: Country (US/India/both), Airline, Airport, Month — applied across all tabs.

---

## Quick Start

### Prerequisites
- Python 3.10+ (tested on 3.14)
- pip

### Install & Run

```bash
# Clone the repo
git clone https://github.com/mark-alexander-hub/Flight-Predictor-Model.git
cd Flight-Predictor-Model

# Install dependencies
pip install -r requirements.txt

# Download and prepare data
python -m data_pipeline.download_us      # Downloads ~3GB from BTS (takes ~15 min)
python -m data_pipeline.download_india   # Generates sample data (or uses Kaggle/local CSV)
python -m data_pipeline.merge            # Combines into unified_flights.csv

# Launch the dashboard
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Architecture

```
SkyPulse/
│
├── app.py                          # Streamlit entry point + page routing
├── config.py                       # Constants: costs, carrier maps, map centers
├── requirements.txt                # Python dependencies
│
├── data_pipeline/                  # Data ingestion & transformation
│   ├── schema.py                   # Unified 23-column schema + validation
│   ├── download_us.py              # BTS On-Time Performance → us_flights.csv
│   ├── download_india.py           # DGCA/Kaggle/sample → india_flights.csv
│   └── merge.py                    # Concatenate → unified_flights.csv
│
├── pages/                          # One module per dashboard tab
│   ├── intro.py                    # Summary metrics
│   ├── map_view.py                 # Folium interactive map
│   ├── delay_reasons.py            # Plotly grouped bar charts
│   ├── heatmap.py                  # Plotly imshow heatmaps
│   ├── time_series.py              # Plotly line charts (frequency + cost)
│   ├── box_plots.py                # Plotly box plots
│   └── data_table.py              # st.dataframe interactive table
│
├── utils/                          # Shared utilities
│   ├── data_loader.py              # @st.cache_data CSV loading
│   └── filters.py                  # Reusable sidebar filter widgets
│
├── data/                           # Generated data (git-ignored)
│   ├── raw/                        # Downloaded BTS zips & India CSVs
│   ├── us_flights.csv              # Processed US data
│   ├── india_flights.csv           # Processed India data
│   └── unified_flights.csv         # Merged final dataset
│
└── (legacy R app)                  # Original R Shiny files (preserved)
    ├── global.R
    ├── server.R
    ├── ui.R
    └── Flight_Delay-master.Rproj
```

---

## Data Pipeline

### Unified Schema (23 columns)

| Column | Type | Description |
|--------|------|-------------|
| `COUNTRY` | str | "US" or "India" |
| `CURRENCY` | str | "USD" or "INR" |
| `AIRLINE` | str | Airline name (e.g., "American", "IndiGo") |
| `ORIGIN` | str | 3-letter IATA airport code |
| `AIRPORT` | str | Full airport name |
| `LATITUDE` | float | Airport latitude |
| `LONGITUDE` | float | Airport longitude |
| `STATE` | str | State/region abbreviation |
| `CITY` | str | City name |
| `OP_CARRIER_FL_NUM` | str | Flight number |
| `FL_DATE` | str | Flight date (YYYY-MM-DD) |
| `Date` | str | Same as FL_DATE |
| `Month` | int | 1-12 |
| `Weekday` | str | Sunday through Saturday (ordered) |
| `Hour` | int | Departure hour (0-23) |
| `ARR_DELAY` | float | Arrival delay in minutes |
| `Sum_Delay_Min` | float | Total delay (sum of 5 reasons) |
| `Direct_Aircraft_Operating_Cost_per_min` | float | $74.2 (US) / ₹45.0 (India) |
| `CARRIER_DELAY` | float | Carrier-caused delay minutes |
| `WEATHER_DELAY` | float | Weather-caused delay minutes |
| `NAS_DELAY` | float | National Aviation System delay minutes |
| `SECURITY_DELAY` | float | Security-caused delay minutes |
| `LATE_AIRCRAFT_DELAY` | float | Late aircraft delay minutes |

### Data Sources

**US (Bureau of Transportation Statistics)**
- Source: [BTS On-Time Reporting](https://www.transtats.bts.gov/)
- Coverage: All US domestic carriers, all airports, 2024
- Pipeline: `download_us.py` downloads 12 monthly ZIP files (~250MB each), extracts CSVs, filters to delayed flights (ARR_DELAY > 0 with at least one delay reason), joins airport coordinates from OpenFlights, samples to 500K rows
- Raw data: ~7M flights → ~1.4M delayed → 500K sampled

**India**
- Default: Synthetic sample data (50K flights, 7 airlines, 20 airports)
- To use real data: place a CSV in `data/raw/india/` — the pipeline auto-detects column names
- Supports Kaggle API download if `kaggle` package is installed
- Delay reason mapping: Indian categories mapped to BTS 5-category system

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Dashboard | [Streamlit](https://streamlit.io) | Web app framework |
| Charts | [Plotly Express](https://plotly.com/python/) | Interactive visualizations |
| Maps | [Folium](https://python-visualization.github.io/folium/) | Leaflet-based interactive maps |
| Data | [Pandas](https://pandas.pydata.org/) | Data manipulation |
| HTTP | [Requests](https://requests.readthedocs.io/) | BTS data downloads |
| Map tiles | CartoDB Positron | Clean, minimal basemap |

---

## Configuration

All constants live in `config.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `US_COST_PER_MIN` | $74.2 | Direct aircraft operating cost (USD) |
| `INDIA_COST_PER_MIN` | ₹45.0 | Direct aircraft operating cost (INR) |
| `CARRIER_MAP_US` | dict | BTS 2-letter code → airline name (22 carriers) |
| `CARRIER_MAP_INDIA` | dict | Indian carrier code → airline name (11 carriers) |
| `WEEKDAY_ORDER` | list | Sunday-first ordering |

---

## Adding New Data

### New country
1. Create `data_pipeline/download_<country>.py`
2. Transform data to the 23-column unified schema
3. Add the CSV path to `data_pipeline/merge.py`
4. Run `python -m data_pipeline.merge`

### Real Indian data
1. Download a flight delay CSV from [Kaggle](https://www.kaggle.com/) or [DGCA](https://www.dgca.gov.in/)
2. Place it in `data/raw/india/`
3. Run `python -m data_pipeline.download_india` — auto-detects columns
4. Run `python -m data_pipeline.merge`

### Update US data to a new year
Edit `YEAR` in `data_pipeline/download_us.py` and re-run.

---

## Roadmap

- [ ] **ML Prediction** — Train Random Forest/XGBoost to predict delay probability
- [ ] **Real India Data** — Replace synthetic with DGCA/Kaggle data
- [ ] **Route Analysis** — City-pair delay patterns
- [ ] **Weather Integration** — Add weather as prediction feature
- [ ] **Deploy** — Streamlit Cloud or similar
- [ ] **Multi-year** — Pull 2019-2024 BTS data for trend analysis

---

## Legacy

This project started as an R Shiny dashboard for Mark's master's thesis (2018 US flight delay data, American & Delta airlines only). The original R files (`global.R`, `server.R`, `ui.R`) are preserved in the repo for reference. The Python rebuild (SkyPulse) expands coverage to all major US airlines + Indian carriers with 2024 data.

---

## License

MIT
