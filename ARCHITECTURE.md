# SkyPulse — Architecture Document

## Overview

SkyPulse is a flight delay analysis dashboard built with Python and Streamlit. It ingests flight delay data from multiple countries (currently US and India), normalizes it to a unified schema, and serves interactive visualizations through a web interface.

```
┌─────────────────────────────────────────────────────────┐
│                     DATA SOURCES                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  BTS (US)    │  │ DGCA (India) │  │  Future...   │  │
│  │  ZIP/CSV     │  │ CSV/Kaggle   │  │              │  │
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
│  │  us_flights + india_flights     │                    │
│  │  → unified_flights.csv          │                    │
│  └─────────────┬───────────────────┘                    │
└────────────────┼────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                  STREAMLIT APP                           │
│                                                          │
│  ┌──────────┐    ┌──────────────────────────────────┐   │
│  │  app.py  │───▶│  utils/data_loader.py             │   │
│  │ (entry)  │    │  @st.cache_data                   │   │
│  └────┬─────┘    └──────────────────────────────────┘   │
│       │                                                  │
│       ▼          ┌──────────────────────────────────┐   │
│  ┌──────────┐    │  utils/filters.py                 │   │
│  │ sidebar  │───▶│  country / airline / airport /    │   │
│  │ nav +    │    │  month filter widgets             │   │
│  │ filters  │    └──────────────────────────────────┘   │
│  └────┬─────┘                                           │
│       │                                                  │
│       ▼  (page routing)                                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │                   pages/                          │   │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────────────┐  │   │
│  │  │intro.py │ │map_view  │ │delay_reasons.py   │  │   │
│  │  │         │ │.py       │ │                    │  │   │
│  │  └─────────┘ └──────────┘ └───────────────────┘  │   │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────────────┐  │   │
│  │  │heatmap  │ │time_     │ │box_plots.py       │  │   │
│  │  │.py      │ │series.py │ │                    │  │   │
│  │  └─────────┘ └──────────┘ └───────────────────┘  │   │
│  │  ┌──────────────┐                                 │   │
│  │  │data_table.py │                                 │   │
│  │  └──────────────┘                                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
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

#### `download_india.py` — India Pipeline
```
Source priority: local CSV → Kaggle API → synthetic sample
→ normalize column names (handles various Kaggle schemas)
→ map delay categories to BTS 5-category system
→ join Indian airport coordinates (same OpenFlights source)
→ write india_flights.csv
```

**Key design decisions:**
- Generates synthetic sample data if no real source found (app works out of box)
- Column detection is fuzzy — handles "delay", "arr_delay", "delay_minutes" etc.
- Graceful fallback: if delay breakdown unavailable, sets all 5 reasons to 0

#### `merge.py` — Concatenation
- Reads `us_flights.csv` and `india_flights.csv`
- Concatenates with `pd.concat`
- Runs `validate()` on the result
- Writes `unified_flights.csv` (93 MB for 550K rows)

---

### 2. Streamlit App

#### `app.py` — Entry Point
- Sets page config (title, icon, wide layout)
- Loads data via cached `load_data()` — CSV read once, survives Streamlit reruns
- Renders sidebar: navigation radio + country filter
- Routes to the correct page module based on selection
- Pages imported lazily (only the active page module loads)

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

### 3. Page Modules (`pages/`)

Each page module exports a single `render(df: pd.DataFrame)` function. The DataFrame passed in is already filtered by country (from the sidebar).

| Module | Visualization | Library | Key Aggregation |
|--------|--------------|---------|-----------------|
| `intro.py` | st.metric cards | Streamlit | Per-country counts, means |
| `map_view.py` | CircleMarker map | Folium | Group by airport → mean delay/cost |
| `delay_reasons.py` | Grouped bar chart | Plotly | Melt 5 delay cols → group by Month+Reason → mean |
| `heatmap.py` | Heatmap (imshow) | Plotly | Group by Weekday+Hour → count |
| `time_series.py` | Line chart | Plotly | Group by date → count / sum cost |
| `box_plots.py` | Box plot | Plotly | Delay_Hours by Month/Weekday/Hour |
| `data_table.py` | Interactive table | Streamlit | No aggregation (raw rows) |

**Pattern**: Each page follows a consistent layout:
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
render(filtered_df) → page-specific filters + aggregation + chart
         │
         ▼
Browser renders updated Plotly/Folium/Streamlit components
```

**Performance notes:**
- CSV loaded once via `@st.cache_data` (~2s for 93MB file, then instant)
- Aggregations happen on every rerun but are fast (pandas on 550K rows < 100ms)
- Folium map is the slowest component (~1s render for 358 airports)
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
1. Create `pages/<name>.py` with a `render(df)` function
2. Add the page name to the `st.sidebar.radio` list in `app.py`
3. Add the import + routing in `app.py`

### Adding ML prediction (planned)
The plan is to:
1. Train a model (Random Forest / XGBoost) on the unified dataset
2. Features: airline, origin airport, month, day of week, hour
3. Target: delay probability + estimated minutes
4. Add a "Predict" tab that takes user inputs and shows predictions
5. Model saved as pickle, loaded with `@st.cache_resource`

---

## File Sizes (typical)

| File | Size | Rows |
|------|------|------|
| `data/raw/ontime_2024_*.csv` | ~260MB each (x12) | ~590K each |
| `data/us_flights.csv` | ~85MB | 500K |
| `data/india_flights.csv` | ~8MB | 50K |
| `data/unified_flights.csv` | ~93MB | 550K |

Total raw data: ~3.1 GB. Total processed: ~93 MB. All git-ignored.
