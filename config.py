"""Central configuration for the Flight Delay Dashboard."""

# Direct aircraft operating cost per minute
US_COST_PER_MIN = 74.2    # USD — source: Airlines for America (A4A)
INDIA_COST_PER_MIN = 45.0  # INR — estimated from Indian airline industry reports

# Weekday ordering (Sunday-first, matching the original R app)
WEEKDAY_ORDER = [
    "Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday",
]

# Map centers
US_MAP_CENTER = (39.82, -98.58)
INDIA_MAP_CENTER = (20.59, 78.96)
WORLD_MAP_CENTER = (25.0, 30.0)

# BTS carrier code → airline name mapping
CARRIER_MAP_US = {
    "AA": "American", "DL": "Delta", "UA": "United",
    "WN": "Southwest", "B6": "JetBlue", "AS": "Alaska",
    "NK": "Spirit", "F9": "Frontier", "G4": "Allegiant",
    "HA": "Hawaiian", "SY": "Sun Country", "MX": "Breeze",
    "QX": "Horizon Air", "OH": "PSA Airlines", "OO": "SkyWest",
    "YV": "Mesa Airlines", "YX": "Republic Airways",
    "9E": "Endeavor Air", "MQ": "Envoy Air", "PT": "Piedmont",
    "ZW": "Air Wisconsin", "C5": "CommutAir",
}

# Indian carrier code → airline name mapping
CARRIER_MAP_INDIA = {
    "6E": "IndiGo", "AI": "Air India", "SG": "SpiceJet",
    "UK": "Vistara", "G8": "Go First", "I5": "AirAsia India",
    "QP": "Akasa Air", "S5": "Star Air", "2T": "TruJet",
    "IX": "Air India Express", "AX": "ACT Airlines",
}

# Delay reason descriptions (shared across US & India)
DELAY_REASON_DESCRIPTIONS = {
    "CARRIER_DELAY": "Delay caused by the carrier — aircraft cleaning, damage, baggage loading, crew issues.",
    "LATE_AIRCRAFT_DELAY": "Delay caused by previous flight arriving late (ripple/reactionary effect).",
    "NAS_DELAY": "Delay caused by the National Aviation System — ATC, airport operations, airspace congestion.",
    "SECURITY_DELAY": "Delay due to security — terminal evacuation, re-boarding after a security breach.",
    "WEATHER_DELAY": "Delay due to weather conditions.",
}
