
import time
import math
import requests
import plotly.graph_objects as go
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# ==================================================
# Page setup
# ==================================================
st.set_page_config(layout="wide")
st.title("Global Country & Region Comparison Dashboard")

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
    "North America": {
        "Core": ["United States", "Canada", "Mexico"],
        "Central America": ["Panama", "Costa Rica", "Guatemala", "Honduras", "El Salvador", "Nicaragua"],
        "Caribbean": ["Jamaica", "Bahamas", "Cuba", "Dominican Republic", "Haiti"],
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
# HELPERS
# ==================================================
def format_compact(n):
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "N/A"
    for div, suf in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if n >= div:
            return f"{n/div:.1f}{suf}"
    return f"{int(n):,}"

@st.cache_data
def get_countries():
    data = requests.get(
        "https://api.worldbank.org/v2/country?format=json&per_page=400",
        timeout=10,
    ).json()[1]
    countries = {c["name"]: c["id"] for c in data if c["region"]["id"] != "NA"}
    return countries

@st.cache_data
def get_time_series(code, indicator):
    try:
        r = requests.get(
            f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}"
            f"?format=json&per_page=1000&page=1",
            timeout=10,
        )
        js = r.json()
    except Exception:
        return []

    if not isinstance(js, list) or len(js) < 2 or js[1] is None:
        return []

    return sorted(
        [(int(d["date"]), d["value"]) for d in js[1] if d["value"] is not None]
    )

def aggregate_region_series(country_codes, indicator, agg="sum"):
    """Aggregate country time series into one region series"""
    yearly = {}

    for code in country_codes:
        series = get_time_series(code, indicator)
        for year, value in series:
            yearly.setdefault(year, []).append(value)

    if agg == "sum":
        return [(y, sum(vs)) for y, vs in yearly.items()]
    else:
        return [(y, sum(vs) / len(vs)) for y, vs in yearly.items()]

# ==================================================
# SIDEBAR
# ==================================================
st.sidebar.header("Controls")

mode = st.sidebar.radio(
    "Mode",
    ["-- Live", "- Static"],
)

if mode.startswith("--"):
    st_autorefresh(interval=5_000, key="refresh")

countries = get_countries()

selection_mode = st.sidebar.radio(
    "Selection",
    ["Manual", "By Region", "By Bloc"]
)

selected_groups = {}

if selection_mode == "Manual":
    selected = st.sidebar.multiselect(
        "Countries",
        list(countries.keys()),
        ["United States", "China", "Germany"],
        max_selections=6,
    )
    selected_groups = {"Selected": selected}

elif selection_mode == "By Region":
    cont = st.sidebar.selectbox("Continent", list(REGIONS.keys()))
    sub = st.sidebar.selectbox("Sub-region", list(REGIONS[cont].keys()))
    selected_groups = {sub: REGIONS[cont][sub]}

elif selection_mode == "By Bloc":
    bloc = st.sidebar.selectbox("Bloc", list(SPECIAL_BLOCKS.keys()))
    selected_groups = {bloc: SPECIAL_BLOCKS[bloc]}

# Filter invalid countries
for k in selected_groups:
    selected_groups[k] = [c for c in selected_groups[k] if c in countries]

# ==================================================
# STATIC MODE — REGION VS REGION TRENDS
# ==================================================
if mode.startswith("-"):
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

    for region_name, country_list in selected_groups.items():
        codes = [countries[c] for c in country_list]
        series = aggregate_region_series(codes, indicator, agg)

        if len(series) < 2:
            continue

        years = [y for y, _ in series]
        values = [v for _, v in series]

        fig.add_trace(go.Scatter(
            x=years,
            y=values,
            mode="lines",
            name=region_name,
        ))
        has_data = True

    if has_data:
        fig.update_layout(
            title=f"Region vs Region – {label}",
            hovermode="x unified",
            yaxis_title=label,
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.warning("Insufficient historical data for selected regions.")

st.caption("Data source: World Bank • Aggregated region-level trends")
