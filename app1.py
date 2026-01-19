# PASTE YOUR FULL STREAMLIT APP CODE HERE


import time
import requests
from datetime import datetime
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# --------------------------------------------------
# Page setup
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("Live Population Metrics (Estimated)")
st.caption("Based on World Bank data with interpolated demographic rates")

# refresh every 5 seconds (Streamlit-native)
st_autorefresh(interval=5_000, key="refresh")


# --------------------------------------------------
# Data helpers
# --------------------------------------------------
@st.cache_data
def get_countries():
    url = "https://api.worldbank.org/v2/country?format=json&per_page=400"
    data = requests.get(url, timeout=10).json()[1]
    countries = {
        c["name"]: c["id"]
        for c in data
        if c["region"]["id"] != "NA"
    }
    countries["World"] = "WLD"
    return dict(sorted(countries.items()))

@st.cache_data
def get_latest_population(country_code):
    url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/SP.POP.TOTL?format=json"
    data = requests.get(url, timeout=10).json()
    latest = next(d for d in data[1] if d["value"] is not None)
    return latest["value"]

def scale_rate(global_rate, country_pop, world_pop):
    return global_rate * (country_pop / world_pop)

# --------------------------------------------------
# Country selection
# --------------------------------------------------
countries = get_countries()

selected_names = st.multiselect(
    "Select countries to compare",
    list(countries.keys()),
    default=["World", "United States", "India", "China"],
    max_selections=5,
)

# --------------------------------------------------
# Baseline population
# --------------------------------------------------
world_pop = get_latest_population("WLD")

country_pops = {
    name: get_latest_population(countries[name])
    for name in selected_names
}

# --------------------------------------------------
# Global demographic estimates
# --------------------------------------------------
GLOBAL_BIRTHS = 140_000_000
GLOBAL_DEATHS = 60_000_000
SECONDS_PER_YEAR = 365 * 24 * 3600

# --------------------------------------------------
# Session timing
# --------------------------------------------------
if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()

if "year_seconds" not in st.session_state:
    start_of_year = datetime(datetime.now().year, 1, 1)
    st.session_state.year_seconds = (datetime.now() - start_of_year).total_seconds()

elapsed = time.time() - st.session_state.start_time

# --------------------------------------------------
# Compute metrics per country
# --------------------------------------------------
today_data = {"Births Today": [], "Deaths Today": [], "Growth Today": []}
year_data = {"Births This Year": [], "Deaths This Year": [], "Growth This Year": []}

for name in selected_names:
    pop = country_pops[name]

    births_year = scale_rate(GLOBAL_BIRTHS, pop, world_pop)
    deaths_year = scale_rate(GLOBAL_DEATHS, pop, world_pop)
    growth_year = births_year - deaths_year

    births_ps = births_year / SECONDS_PER_YEAR
    deaths_ps = deaths_year / SECONDS_PER_YEAR
    growth_ps = growth_year / SECONDS_PER_YEAR

    today_data["Births Today"].append(births_ps * elapsed)
    today_data["Deaths Today"].append(deaths_ps * elapsed)
    today_data["Growth Today"].append(growth_ps * elapsed)

    year_data["Births This Year"].append(births_ps * st.session_state.year_seconds + births_ps * elapsed)
    year_data["Deaths This Year"].append(deaths_ps * st.session_state.year_seconds + deaths_ps * elapsed)
    year_data["Growth This Year"].append(growth_ps * st.session_state.year_seconds + growth_ps * elapsed)

# --------------------------------------------------
# Tabs layout
# --------------------------------------------------
tab1, tab2 = st.tabs(["Charts", "Map"])

# --------------------------------------------------
# TAB 1 — Charts
# --------------------------------------------------
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        fig_today = go.Figure()
        for metric, color in zip(
            today_data.keys(),
            ["#2ecc71", "#e74c3c", "#3498db"],
        ):
            fig_today.add_bar(
                name=metric,
                x=selected_names,
                y=today_data[metric],
            )

        fig_today.update_layout(
            title="Today (Live Estimated)",
            barmode="group",
            yaxis_title="People",
        )

        st.plotly_chart(fig_today, width="stretch")

    with col2:
        fig_year = go.Figure()
        for metric, color in zip(
            year_data.keys(),
            ["#27ae60", "#c0392b", "#2980b9"],
        ):
            fig_year.add_bar(
                name=metric,
                x=selected_names,
                y=year_data[metric],
            )

        fig_year.update_layout(
            title="This Year (Live Estimated)",
            barmode="group",
            yaxis_title="People",
        )

        st.plotly_chart(fig_year, width="stretch")

# --------------------------------------------------
# TAB 2 — Map
# --------------------------------------------------
with tab2:
    map_metric = st.selectbox(
        "Map metric",
        ["Population", "Births This Year", "Deaths This Year", "Growth This Year"],
    )

    map_values = {}

    for name, code in countries.items():
        pop = get_latest_population(code)

        births_year = scale_rate(GLOBAL_BIRTHS, pop, world_pop)
        deaths_year = scale_rate(GLOBAL_DEATHS, pop, world_pop)
        growth_year = births_year - deaths_year

        if map_metric == "Population":
            map_values[code] = pop
        elif map_metric == "Births This Year":
            map_values[code] = births_year
        elif map_metric == "Deaths This Year":
            map_values[code] = deaths_year
        elif map_metric == "Growth This Year":
            map_values[code] = growth_year

    fig_map = go.Figure(
        go.Choropleth(
            locations=list(map_values.keys()),
            z=list(map_values.values()),
            locationmode="ISO-3",
            colorscale="Viridis",
            colorbar_title=map_metric,
        )
    )

    fig_map.update_layout(
        title=f"World Map – {map_metric}",
        geo=dict(
            showframe=False,
            showcoastlines=False,
            projection_type="natural earth",
        ),
    )

    st.plotly_chart(fig_map, width="stretch")

# --------------------------------------------------
# Footer
# --------------------------------------------------
st.caption(
    "Values are estimates derived from World Bank population data and global demographic rates. "
    "They are not real-time census counts."
)
