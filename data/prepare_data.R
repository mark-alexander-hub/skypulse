# =============================================================================
# prepare_data.R — Download and prepare BTS On-Time Performance data
# =============================================================================
# This script downloads the latest Bureau of Transportation Statistics (BTS)
# On-Time Reporting data and transforms it into the format expected by the
# Flight Delay dashboard (new_data.csv).
#
# Usage:
#   1. Run this script from RStudio or command line:
#      Rscript data/prepare_data.R
#   2. It will download data for the specified year and produce new_data.csv
#      in the project root.
#
# Data source: BTS On-Time Reporting Carrier On-Time Performance
# https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoession_VQ=FGJ
# =============================================================================

library(dplyr)
library(tidyr)
library(lubridate)
library(readr)

# --- Configuration -----------------------------------------------------------
# Set the year(s) to download. BTS typically has data through ~3 months ago.
# 2024 is the latest full year as of early 2026.
YEAR <- 2024

# Maximum rows to keep (delayed flights only). Set to NULL for all.
# The original dataset had ~310K rows. Keeping it manageable for Shiny.
MAX_ROWS <- 500000

# Output path (relative to project root)
OUTPUT_FILE <- "new_data.csv"

# Direct aircraft operating cost per minute (USD)
# Source: Airlines for America (A4A) — updated estimate
COST_PER_MIN <- 74.2

# --- Airport lookup with coordinates -----------------------------------------
# We need lat/lon for the map. BTS on-time data doesn't include coordinates,
# so we use the BTS airport master list.
get_airport_info <- function() {
  # Download airport data from BTS Master Coordinate table
  url <- "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"

  message("Downloading airport coordinates...")
  airports <- tryCatch({
    read_csv(url, col_names = c(
      "airport_id", "name", "city", "country", "iata", "icao",
      "latitude", "longitude", "altitude", "timezone", "dst",
      "tz_database", "type", "source"
    ), show_col_types = FALSE)
  }, error = function(e) {
    message("Failed to download airport data: ", e$message)
    message("Trying fallback source...")
    # Fallback: use a bundled file if download fails
    NULL
  })

  if (is.null(airports)) {
    stop("Could not download airport coordinates. Check your internet connection.")
  }

  # Filter to US airports with valid IATA codes
  airports <- airports %>%
    filter(country == "United States", iata != "\\N", iata != "") %>%
    select(iata, name, city, latitude, longitude) %>%
    rename(ORIGIN = iata, AIRPORT = name, CITY_COORDS = city,
           LATITUDE = latitude, LONGITUDE = longitude) %>%
    distinct(ORIGIN, .keep_all = TRUE)

  return(airports)
}

# --- Download BTS data -------------------------------------------------------
download_bts_data <- function(year, month) {
  # BTS provides data via their TranStats interface.
  # We use the pre-zipped download URL pattern for the On-Time Reporting table.
  #
  # The URL format for the marketing carrier on-time performance data:
  url <- sprintf(
    "https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_%d_%d.zip",
    year, month
  )

  dest_dir <- "data/raw"
  zip_file <- file.path(dest_dir, sprintf("ontime_%d_%d.zip", year, month))
  csv_file <- file.path(dest_dir, sprintf("ontime_%d_%d.csv", year, month))

  # Skip if already downloaded and extracted
  if (file.exists(csv_file)) {
    message(sprintf("  Month %d: already downloaded, skipping.", month))
    return(csv_file)
  }

  message(sprintf("  Downloading %d-%02d...", year, month))

  tryCatch({
    download.file(url, zip_file, mode = "wb", quiet = TRUE)

    # Extract the CSV from the zip
    csv_names <- unzip(zip_file, list = TRUE)$Name
    csv_name <- csv_names[grepl("\\.csv$", csv_names)][1]
    unzip(zip_file, files = csv_name, exdir = dest_dir)

    # Rename to our convention
    extracted_path <- file.path(dest_dir, csv_name)
    if (extracted_path != csv_file) {
      file.rename(extracted_path, csv_file)
    }

    # Clean up zip
    file.remove(zip_file)

    return(csv_file)
  }, error = function(e) {
    message(sprintf("  Failed to download month %d: %s", month, e$message))
    if (file.exists(zip_file)) file.remove(zip_file)
    return(NULL)
  })
}

# --- Main pipeline -----------------------------------------------------------
main <- function() {
  message(sprintf("=== Preparing Flight Delay Data for %d ===\n", YEAR))

  # Step 1: Get airport coordinates
  airports <- get_airport_info()
  message(sprintf("Loaded %d US airport coordinates.\n", nrow(airports)))

  # Step 2: Download monthly BTS data
  message(sprintf("Downloading BTS On-Time Performance data for %d...", YEAR))
  csv_files <- c()
  for (month in 1:12) {
    f <- download_bts_data(YEAR, month)
    if (!is.null(f)) csv_files <- c(csv_files, f)
  }

  if (length(csv_files) == 0) {
    stop("No data files were downloaded. Check your internet connection and that data exists for the specified year.")
  }
  message(sprintf("\nDownloaded %d months of data.\n", length(csv_files)))

  # Step 3: Read and combine all months
  message("Reading and combining monthly files...")

  # Columns we need from BTS data
  cols_needed <- c(
    "OP_UNIQUE_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN",
    "ORIGIN_CITY_NAME", "ORIGIN_STATE_ABR",
    "FL_DATE", "DEP_TIME", "DAY_OF_WEEK",
    "ARR_DELAY", "CARRIER_DELAY", "WEATHER_DELAY",
    "NAS_DELAY", "SECURITY_DELAY", "LATE_AIRCRAFT_DELAY"
  )

  all_data <- lapply(csv_files, function(f) {
    message(sprintf("  Reading %s...", basename(f)))
    df <- read_csv(f, show_col_types = FALSE, guess_max = 10000)

    # Only keep columns we need (some may be missing in older data)
    available_cols <- intersect(cols_needed, names(df))
    df <- df %>% select(all_of(available_cols))
    return(df)
  })

  raw_df <- bind_rows(all_data)
  message(sprintf("\nTotal raw records: %s", format(nrow(raw_df), big.mark = ",")))

  # Step 4: Filter to delayed flights only
  # A flight is "delayed" if ARR_DELAY > 0 and at least one delay reason is present
  message("Filtering to delayed flights...")

  delay_cols <- c("CARRIER_DELAY", "WEATHER_DELAY", "NAS_DELAY",
                  "SECURITY_DELAY", "LATE_AIRCRAFT_DELAY")

  delayed_df <- raw_df %>%
    filter(ARR_DELAY > 0) %>%
    filter(if_any(all_of(delay_cols), ~ !is.na(.) & . > 0))

  message(sprintf("Delayed flights: %s", format(nrow(delayed_df), big.mark = ",")))

  # Step 5: Transform to match expected schema
  message("Transforming data...")

  # Map carrier codes to airline names
  # BTS uses 2-letter carrier codes. Here are the major ones:
  carrier_map <- c(
    "AA" = "American", "DL" = "Delta", "UA" = "United",
    "WN" = "Southwest", "B6" = "JetBlue", "AS" = "Alaska",
    "NK" = "Spirit", "F9" = "Frontier", "G4" = "Allegiant",
    "HA" = "Hawaiian", "SY" = "Sun Country", "MX" = "Breeze",
    "QX" = "Horizon Air", "OH" = "PSA Airlines", "OO" = "SkyWest",
    "YV" = "Mesa Airlines", "YX" = "Republic Airways",
    "9E" = "Endeavor Air", "MQ" = "Envoy Air", "PT" = "Piedmont",
    "ZW" = "Air Wisconsin", "C5" = "CommutAir",
    "CP" = "Compass Airlines", "EM" = "Empire Airlines"
  )

  flight_df <- delayed_df %>%
    mutate(
      # Map airline codes to names (keep code if not in map)
      AIRLINE = ifelse(OP_UNIQUE_CARRIER %in% names(carrier_map),
                       carrier_map[OP_UNIQUE_CARRIER],
                       OP_UNIQUE_CARRIER),

      # Parse date components
      FL_DATE_parsed = as.Date(FL_DATE),
      Month = month(FL_DATE_parsed),
      Weekday = wday(FL_DATE_parsed, label = TRUE, abbr = FALSE),
      Date = as.character(FL_DATE_parsed),

      # Extract hour from departure time (HHMM format)
      Hour = as.integer(DEP_TIME) %/% 100,

      # Replace NA delay columns with 0
      across(all_of(delay_cols), ~ replace_na(., 0)),

      # Total delay minutes
      Sum_Delay_Min = CARRIER_DELAY + WEATHER_DELAY + NAS_DELAY +
        SECURITY_DELAY + LATE_AIRCRAFT_DELAY,

      # Cost per minute
      Direct_Aircraft_Operating_Cost_per_min = COST_PER_MIN,

      # Extract state and city from ORIGIN_CITY_NAME (format: "City, ST")
      STATE = ORIGIN_STATE_ABR,
      CITY = sub(",.*", "", ORIGIN_CITY_NAME)
    ) %>%
    # Filter out invalid hours
    filter(!is.na(Hour), Hour >= 0, Hour <= 23) %>%
    # Drop rows with no origin
    filter(!is.na(ORIGIN))

  # Step 6: Join airport coordinates
  message("Joining airport coordinates...")
  flight_df <- flight_df %>%
    left_join(airports %>% select(ORIGIN, AIRPORT, LATITUDE, LONGITUDE),
              by = "ORIGIN")

  # Drop flights where we couldn't find coordinates
  n_before <- nrow(flight_df)
  flight_df <- flight_df %>% filter(!is.na(LATITUDE))
  message(sprintf("  Dropped %d flights with unknown airport coordinates.",
                  n_before - nrow(flight_df)))

  # Step 7: Select and order final columns
  flight_df <- flight_df %>%
    select(
      AIRLINE, ORIGIN, AIRPORT, LATITUDE, LONGITUDE, STATE, CITY,
      OP_CARRIER_FL_NUM, FL_DATE = Date, Date, Month, Weekday, Hour,
      ARR_DELAY, Sum_Delay_Min, Direct_Aircraft_Operating_Cost_per_min,
      CARRIER_DELAY, WEATHER_DELAY, NAS_DELAY, SECURITY_DELAY,
      LATE_AIRCRAFT_DELAY
    )

  # Step 8: Sample if too large
  if (!is.null(MAX_ROWS) && nrow(flight_df) > MAX_ROWS) {
    message(sprintf("Sampling %s rows from %s total...",
                    format(MAX_ROWS, big.mark = ","),
                    format(nrow(flight_df), big.mark = ",")))
    set.seed(42)
    flight_df <- flight_df %>% sample_n(MAX_ROWS)
  }

  # Step 9: Write output
  message(sprintf("\nWriting %s (%s rows)...",
                  OUTPUT_FILE, format(nrow(flight_df), big.mark = ",")))
  write_csv(flight_df, OUTPUT_FILE)

  # Summary
  message("\n=== Done! ===")
  message(sprintf("Airlines: %s", paste(sort(unique(flight_df$AIRLINE)), collapse = ", ")))
  message(sprintf("Airports: %d unique origins", n_distinct(flight_df$ORIGIN)))
  message(sprintf("Date range: %s to %s", min(flight_df$FL_DATE), max(flight_df$FL_DATE)))
  message(sprintf("Total delayed flights: %s", format(nrow(flight_df), big.mark = ",")))
  message(sprintf("\nOutput: %s (%.1f MB)",
                  OUTPUT_FILE,
                  file.size(OUTPUT_FILE) / 1024^2))
}

# Run it
main()
