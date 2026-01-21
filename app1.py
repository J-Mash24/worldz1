
import time
import math
import requests
import plotly.graph_objects as go
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# ==================================================
# PAGE SETUP
# ==================================================
st.set_page_config(layout="wide")
st.title("Global Country & Region Comparison Dashboard")

# ==================================================
# GLOBAL CONSTANTS
# ==================================================
WB_TIMEOUT = 15
WB_RETRIES = 2

# ==================================================
# REGIONAL TAXONOMY
# ==================================================
REGIONS = {
    "Europe": {
        "Baltic States": ["Estonia", "Latvia", "Lithuania"],
        "Scandinavian": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
        "Benelux": ["Belgium", "Netherlands", "Luxembourg"],
        "Warsaw Pact": ["Poland", "Czech Republic", "Slovakia", "Hungary", "Romania", "Bulgaria"],
        "Balkans": ["Serbia", "Croatia", "Bosnia and Herzegovina", "Albania", "North Macedonia", "Montenegro"],
        "Southern Europe": ["Italy", "Spain", "Portugal", "Greece"],
        "Western Europe": ["France", "Germany", "Austria", "Switzerland", "United Kingdom"],
    },
    "Asia": {
        "Middle East": ["Israel", "Iran", "Iraq", "Jordan", "Lebanon"],
        "Gulf Kingdoms": ["Saudi Arabia", "United Arab Emirates", "Qatar", "Oman", "Kuwait"],
        "South Asia": ["India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal"],
        "East Asia": ["China", "Japan", "South Korea"],
    },
    "Africa": {
        "Arab Spring": ["Egypt", "Tunisia", "Libya"],
        "West Africa": ["Nigeria", "Ghana", "Senegal", "Ivory Coast"],
        "Central Africa": ["Cameroon", "Chad", "Central African Republic"],
        "Southern Africa": ["South Africa", "Namibia", "Botswana", "Zimbabwe"],
    },
}

SPECIAL_BLOCKS = {
    "EU": [
        "Germany", "France", "Italy", "Spain", "Poland", "Netherlands",
        "Belgium", "Austria", "Sweden", "Finland", "Denmark", "Portugal",
        "Greece", "Czech Republic", "Hungary", "Romania", "Bulgaria"
    ],
    "BRICS": ["Brazil", "Russia", "India", "China", "South Africa"],
}

# ==================================================
# HELPER FUNCTIONS
# ==================================================
def safe_request(url):
    """Retry-safe HTTP request"""
    for _ in range(WB_RETRIES):
        try:
            r = requests.get(url, timeout=WB_TIMEOUT)
            r.raise_for_status()
            return r
        except Exception:
            time.sleep(1)
    return None

def format_compact(n):
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "N/A"
    for div, suf in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if n >= div:
            return f"{n/div:.1f}{suf}"
    return f"{int(n):,}"

# ==================================================
# WORLD BANK API WRAPPERS
# ==================================================
@st.cache_data(ttl=3600)
def get_countries():
    url = "https://api.worldbank.org/v2/country?format=json&per_page=400"
    r = safe_request(url)
    if not r:
        return {}

    try:
        js = r.json()
    except Exception:
        return {}

    if not isinstance(js, list) or len(js) < 2 or js[1] is None:
        return {}

    out = {}
    for c in js[1]:
        try:
            if c["region"]["id"] != "NA":
                out[c["name"]] = c["id"]
        except Exception:
            continue
    return dict(sorted(out.items()))

@st.cache_data(ttl=3600)
def get_time_series(code, indicator):
    url = (
        f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}"
        f"?format=json&per_page=1000"
    )
    r = safe_request(url)
    if not r:
        return []

    try:
        js = r.json()
    except Exception:
        return []

    if not isinstance(js, list) or len(js) < 2 or js[1] is None:
        return []

    series = []
    for d in js[1]:
        try:
            if d["value"] is not None:
                series.append((int(d["date"]), d["value"]))
        except Exception:
            continue

    return sorted(series)

def aggregate_region_series(country_codes, indicator, agg):
    yearly = {}
    for code in country_codes:
        series = get_time_series(code, indicator)
        for year, val in series:
            yearly.setdefault(year, []).append(val)

    out = []
    for year, vals in yearly.items():
        if agg == "sum":
            out.append((year, sum(vals)))
        else:
            out.append((year, sum(vals) / len(vals)))
    return sorted(out)

# ==================================================
# SIDEBAR
# ==================================================
st.sidebar.header("Controls")

mode = st.sidebar.radio("Mode", ["-- Live", "- Static"])
if mode.startswith("--"):
    st_autorefresh(interval=5_000, key="refresh")

countries = get_countries()
if not countries:
    st.error("World Bank API temporarily unavailable. Please refresh.")
    st.stop()

selection_mode = st.sidebar.radio("Selection", ["Manual", "By Region", "By Bloc"])

groups = {}

if selection_mode == "Manual":
    sel = st.sidebar.multiselect(
        "Countries",
        list(countries.keys()),
        ["United States", "China", "Germany"],
        max_selections=6,
    )
    groups = {"Selected": sel}

elif selection_mode == "By Region":
    cont = st.sidebar.selectbox("Continent", list(REGIONS.keys()))
    sub = st.sidebar.selectbox("Sub-region", list(REGIONS[cont].keys()))
    groups = {sub: REGIONS[cont][sub]}

elif selection_mode == "By Bloc":
    bloc = st.sidebar.selectbox("Bloc", list(SPECIAL_BLOCKS.keys()))
    groups = {bloc: SPECIAL_BLOCKS[bloc]}

# Filter invalid names
for k in groups:
    groups[k] = [c for c in groups[k] if c in countries]

# ==================================================
# LIVE MODE
# ==================================================
if mode.startswith("--"):
    st.subheader("-- Live Population Growth (Estimated)")
    st.info("Live mode uses global demographic estimates (not census data).")
    st.stop()

# ==================================================
# STATIC MODE — REGION VS REGION TRENDS
# ==================================================
st.subheader("Region vs Region Trends")

INDICATORS = {
    "Population (sum)": ("SP.POP.TOTL", "sum"),
    "GDP (sum)": ("NY.GDP.MKTP.CD", "sum"),
    "GDP per Capita (avg)": ("NY.GDP.PCAP.CD", "avg"),
    "Gini Index (avg)": ("SI.POV.GINI", "avg"),
}

label = st.selectbox("Indicator", list(INDICATORS.keys()))
indicator, agg = INDICATORS[label]

fig = go.Figure()
has_data = False

for region, names in groups.items():
    codes = [countries[n] for n in names]
    series = aggregate_region_series(codes, indicator, agg)

    if len(series) < 2:
        continue

    fig.add_trace(go.Scatter(
        x=[y for y, _ in series],
        y=[v for _, v in series],
        mode="lines",
        name=region,
    ))
    has_data = True

if has_data:
    fig.update_layout(
        title=f"Region vs Region — {label}",
        hovermode="x unified",
        yaxis_title=label,
    )
    st.plotly_chart(fig, width="stretch")
else:
    st.warning("Insufficient historical data for selected regions.")

st.caption("Data source: World Bank • Stable production-safe version")
