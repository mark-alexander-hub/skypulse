# SkyPulse — Architecture Document

## Overview

SkyPulse is a flight delay analysis dashboard with ML prediction, built with Python and Streamlit. It ingests flight delay data from multiple countries (US and India), normalizes it to a unified schema, trains ML models, and serves interactive visualizations through a web interface.

```
┌─────────────────────────────────────────────────────────┐
│                     DATA SOURCES                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  BTS (US)    │  │ DGCA (India) │  │  Future...   │  │
│  │  ZIP/CSV     │  │ OTP rates    │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                   DATA PIPELINE                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │download_us.py│  │download_     │  │  schema.py   │  │
│  │              │  │india.py      │  │  (validation)│  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘  │
│         │                  │                             │
│         ▼                  ▼                             │
│  ┌─────────────────────────────────┐                    │
│  │         merge.py                │                    │
│  │  → unified_flights.csv (620K)   │                    │
│  └─────────────┬───────────────────┘                    │
└────────────────┼────────────────────────────────────────┘
                 │
          ┌──────┴──────┐
          ▼              ▼
┌──────────────┐  ┌──────────────────────────────────────┐
│  ML MODELS   │  │          STREAMLIT APP                │
│              │  │                                        │
│  ml_model.py │  │  ┌──────────┐  ┌─────────────────┐   │
│  ┌─────────┐ │  │  │  app.py  │─▶│ data_loader.py  │   │
│  │ Random  │ │  │  │ (entry)  │  │ @st.cache_data  │   │
│  │ Forest  │ │  │  └────┬─────┘  └─────────────────┘   │
│  │ (clf)   │ │  │       │                                │
│  ├─────────┤ │  │       ▼  (page routing)                │
│  │ XGBoost │ │  │  ┌────────────────────────────────┐   │
│  │ (reg)   │ │  │  │           views/                │   │
│  └─────────┘ │  │  │  intro · predict · map_view     │   │
│  models/*.pkl│  │  │  delay_reasons · heatmap         │   │
│              │  │  │  time_series · box_plots          │   │
│              │  │  │  data_table                       │   │
│              │  │  └────────────────────────────────┘   │
└──────────────┘  └──────────────────────────────────────┘
```

---

## Component Details

### 1. Data Pipeline (`data_pipeline/`)

The pipeline runs **offline** (not during app startup). It downloads, transforms, and merges data into a single CSV that the Streamlit app reads at runtime.

#### `schema.py` — Single Source of Truth
- Defines the 23-column unified schema as a constant list
- Lists the 5 delay reason columns (`DELAY_REASON_COLS`)
- Provides `validate(df)` function that checks column presence and coerces types
- Weekday ordering enforced as ordered pandas Categorical

#### `download_us.py` — BTS Pipeline
```
BTS ZIP (per month) → extract CSV → read into pandas
→ rename CamelCase columns to ALL_CAPS
→ filter: ARR_DELAY > 0 AND any delay reason > 0
→ map carrier codes to airline names
→ parse dates → extract Month, Weekday, Hour
→ compute Sum_Delay_Min, add cost constant
→ join airport coordinates (OpenFlights)
→ sample to 500K rows → write us_flights.csv
```

**Key design decisions:**
- Downloads are cached: if `data/raw/ontime_2024_1.csv` exists, it skips re-downloading
- Column rename handles BTS's CamelCase format (ArrDelay → ARR_DELAY)
- Airport coordinates sourced from OpenFlights GitHub (no API key needed)
- 500K row cap keeps Streamlit responsive; adjustable via `max_rows` param

#### `download_india.py` — DGCA OTP-Calibrated Pipeline
```
Download real DGCA daily OTP CSV from GitHub
→ parse OTP % columns per airline (strip "%" strings)
→ for each (date, airline) record:
    → generate flights proportional to market share (40-350/day)
    → use real OTP rate to determine delayed vs on-time
    → exponential delay distribution (mean 35 min)
    → Dirichlet split across 5 delay categories
    → bimodal departure hour distribution (6-9 AM, 5-9 PM peaks)
→ assign to 20 real Indian airports (weighted by traffic)
→ join coordinates from OpenFlights
→ cap at 120K rows → write india_flights.csv
```

**Key design decisions:**
- Uses **real DGCA on-time performance rates** — not purely synthetic
- 4-tier fallback: DGCA OTP → local CSV → Kaggle API → pure synthetic
- `normalize_indian_data()` handles arbitrary CSV schemas if real flight-level data is placed in `data/raw/india/`

#### `merge.py` — Concatenation
- Reads `us_flights.csv` and `india_flights.csv`
- Concatenates with `pd.concat`
- Runs `validate()` on the result
- Writes `unified_flights.csv` (104 MB for 620K rows)

---

### 2. ML Models (`ml_model.py`)

Two models trained on the unified dataset:

| Model | Algorithm | Target | Performance |
|-------|-----------|--------|-------------|
| Classifier | Random Forest (200 trees, depth 12) | Delayed 30+ min (binary) | 64.6% accuracy (39.1% baseline) |
| Regressor | XGBoost (300 rounds, depth 8) | Delay minutes (continuous) | 44.3 min MAE (48.5 baseline) |

**Features:** COUNTRY, AIRLINE, ORIGIN, Month, Hour, Weekday_num (6 features)

**Feature importances:** Country (36%) > Hour (32%) > Airline (14%) > Origin (8%) > Month (7%) > Weekday (3%)

**Artifacts:** `models/delay_classifier.pkl`, `models/delay_regressor.pkl`, `models/encoders.pkl` (all git-ignored)

**`predict()` function:** Takes country, airline, origin, month, hour, weekday → returns delay_probability, expected_minutes, risk_level (Low/Medium/High).

---

### 3. Streamlit App

#### `app.py` — Entry Point
- Sets page config (title, icon, wide layout)
- Loads data via cached `load_data()` — CSV read once, survives Streamlit reruns
- Renders sidebar: navigation radio (8 tabs) + country filter
- Routes to the correct view module based on selection
- Views imported lazily (only the active module loads)

**Note:** Views are in `views/` not `pages/` — Streamlit auto-detects `pages/` as multipage and creates duplicate navigation. Renaming to `views/` prevents this.

#### `utils/data_loader.py` — Cached Loading
- `@st.cache_data` decorator memoizes the CSV read
- Coerces Weekday to ordered Categorical, Month/Hour to int
- Shows error + stops if `unified_flights.csv` is missing

#### `utils/filters.py` — Shared Filter Widgets
- `country_filter(df)` — multiselect in sidebar, returns filtered DataFrame
- `airline_filter(df, key)` — multiselect or selectbox, returns selection
- `airport_filter(df, key)` — selectbox of IATA codes
- `month_filter(df, key)` — multiselect of months 1-12
- `key` parameter ensures unique Streamlit widget IDs across pages

#### `config.py` — Constants
- Cost per minute by country ($74.2 USD, ₹45.0 INR)
- Carrier code → name mappings (US: 22 carriers, India: 11 carriers)
- Map center coordinates (US, India, World)
- Weekday ordering
- Delay reason human-readable descriptions

---

### 4. View Modules (`views/`)

Each view module exports a single `render(df: pd.DataFrame)` function. The DataFrame passed in is already filtered by country (from the sidebar).

| Module | Visualization | Library | Key Aggregation |
|--------|--------------|---------|-----------------|
| `intro.py` | st.metric cards | Streamlit | Per-country counts, means |
| `predict.py` | Input form + results | Streamlit + ML | Single-flight prediction via ml_model.predict() |
| `map_view.py` | CircleMarker map | Folium | Group by airport → mean delay/cost |
| `delay_reasons.py` | Grouped bar chart | Plotly | Melt 5 delay cols → group by Month+Reason → mean |
| `heatmap.py` | Heatmap (imshow) | Plotly | Group by Weekday+Hour → count |
| `time_series.py` | Line chart | Plotly | Group by date → count / sum cost |
| `box_plots.py` | Box plot | Plotly | Delay_Hours by Month/Weekday/Hour |
| `data_table.py` | Interactive table | Streamlit | No aggregation (raw rows) |

**Pattern**: Each view follows a consistent layout:
1. `st.header()` — page title
2. `st.columns([3, 1])` — chart area (75%) + filter panel (25%)
3. Filter widgets in the right column
4. Chart rendered in the left column
5. Optional descriptive text below

---

## Data Flow

```
User interaction (filter change)
         │
         ▼
Streamlit reruns app.py
         │
         ▼
load_data() → returns cached DataFrame (no re-read)
         │
         ▼
country_filter() → filters by COUNTRY column
         │
         ▼
render(filtered_df) → view-specific filters + aggregation + chart
         │                    │
         │              (Predict tab only)
         │                    ▼
         │              ml_model.predict() → classifier + regressor
         │                    │
         ▼                    ▼
Browser renders updated Plotly/Folium/Streamlit components
```

**Performance notes:**
- CSV loaded once via `@st.cache_data` (~3s for 104MB file, then instant)
- Aggregations happen on every rerun but are fast (pandas on 620K rows < 100ms)
- Folium map is the slowest component (~1s render for 358 airports)
- ML prediction is instant (<50ms per prediction)
- No database needed — everything is in-memory pandas

---

## Extending SkyPulse

### Adding a new country
1. Create `data_pipeline/download_<country>.py` with a `prepare_<country>_data()` function
2. Output must match the 23-column schema in `schema.py`
3. Add airport coordinates from OpenFlights (same source, filter by country)
4. Add the output CSV path to `merge.py`
5. Add carrier map + cost constant to `config.py`

### Adding a new visualization tab
1. Create `views/<name>.py` with a `render(df)` function
2. Add the page name to the `st.sidebar.radio` list in `app.py`
3. Add the import + routing in `app.py`

### Retraining ML models
```bash
python ml_model.py
```
This reads `data/unified_flights.csv`, trains both models, and writes pickles to `models/`.

---

## File Sizes (typical)

| File | Size | Rows |
|------|------|------|
| `data/raw/ontime_2024_*.csv` | ~260MB each (x12) | ~590K each |
| `data/us_flights.csv` | ~85MB | 500K |
| `data/india_flights.csv` | ~20MB | 120K |
| `data/unified_flights.csv` | ~104MB | 620K |
| `models/*.pkl` | ~15MB total | — |

Total raw data: ~3.1 GB. Total processed: ~104 MB. All git-ignored.
