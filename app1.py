
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
st.title("Global Country Comparison Dashboard")

# ==================================================
# HELPERS
# ==================================================
def format_compact(n):
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "N/A"
    if n >= 1e12:
        return f"{n/1e12:.1f}T"
    if n >= 1e9:
        return f"{n/1e9:.1f}B"
    if n >= 1e6:
        return f"{n/1e6:.1f}M"
    if n >= 1e3:
        return f"{n/1e3:.1f}K"
    return f"{int(n):,}"

def index_series(series):
    if len(series) < 2:
        return []
    base_val = series[0][1]
    if base_val in (None, 0):
        return []
    return [(y, v / base_val * 100) for y, v in series]

def growth_badge(val):
    if val is None:
        return "No data"
    if val > 1.5:
        return "Fast growth"
    if val > 0.5:
        return "🟡 Moderate growth"
    return "Slow / shrinking"

@st.cache_data
def get_countries():
    url = "https://api.worldbank.org/v2/country?format=json&per_page=400"
    data = requests.get(url, timeout=10).json()[1]
    countries = {c["name"]: c["id"] for c in data if c["region"]["id"] != "NA"}
    countries["World"] = "WLD"
    return dict(sorted(countries.items()))

@st.cache_data
def get_indicator(code, indicator):
    try:
        r = requests.get(
            f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json",
            timeout=10,
        )
        js = r.json()
    except Exception:
        return None

    if not isinstance(js, list) or len(js) < 2 or js[1] is None:
        return None

    for d in js[1]:
        if d.get("value") is not None:
            return d["value"]
    return None

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

    series = []
    for d in js[1]:
        if d.get("value") is not None:
            series.append((int(d["date"]), d["value"]))
    return sorted(series)

# ==================================================
# SIDEBAR (ALWAYS VISIBLE)
# ==================================================
st.sidebar.header("Controls")

mode = st.sidebar.radio(
    "Dashboard mode",
    ["-- Live (Demographics)", "- Static (Insights & Trends)"]
)

if mode.startswith("--"):
    st_autorefresh(interval=5_000, key="refresh")

countries = get_countries()

STORIES = {
    "None": None,
    "Rise of Asia": {
        "countries": ["China", "India", "Japan", "South Korea"],
        "indicator": "NY.GDP.PCAP.CD",
        "indexed": True,
    },
    "Aging societies": {
        "countries": ["Japan", "Italy", "Germany", "South Korea"],
        "indicator": "SP.POP.TOTL",
        "indexed": True,
    },
}

story = st.sidebar.selectbox("📘 Story preset", list(STORIES.keys()))

selected = st.sidebar.multiselect(
    "Select countries",
    list(countries.keys()),
    ["World", "United States", "China"],
    max_selections=5,
    disabled=(story != "None"),
)

if story != "None":
    selected = STORIES[story]["countries"]

# ==================================================
# 🔴 LIVE MODE
# ==================================================
if mode.startswith("--"):
    st.subheader("-- Live Population Growth (Estimated)")

    GLOBAL_BIRTHS = 140_000_000
    GLOBAL_DEATHS = 60_000_000
    SECONDS_PER_YEAR = 365 * 24 * 3600

    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    elapsed = time.time() - st.session_state.start_time
    world_pop = get_indicator("WLD", "SP.POP.TOTL")

    values = []
    for name in selected:
        pop = get_indicator(countries[name], "SP.POP.TOTL")
        if pop and world_pop:
            growth = (GLOBAL_BIRTHS - GLOBAL_DEATHS) * (pop / world_pop)
            values.append(growth / SECONDS_PER_YEAR * elapsed)
        else:
            values.append(0)

    fig = go.Figure(go.Bar(
        x=selected,
        y=values,
        text=[format_compact(v) for v in values],
        textposition="outside",
    ))

    fig.update_layout(
        title="Estimated population increase since page load",
        yaxis_range=[0, max(values) * 1.3 if values else 1],
        showlegend=False,
    )

    st.plotly_chart(fig, width="stretch")
    st.caption("Live values are extrapolated from annual demographic rates.")

# ==================================================
# ⚪ STATIC MODE
# ==================================================
else:
    INDICATORS = {
        "Population": "SP.POP.TOTL",
        "GDP per Capita": "NY.GDP.PCAP.CD",
        "Gini Index": "SI.POV.GINI",
    }

    rows = []
    for name in selected:
        row = {"Country": name}
        for label, ind in INDICATORS.items():
            row[label] = get_indicator(countries[name], ind)
        rows.append(row)

    df = pd.DataFrame(rows)

    tab_insight, tab_trends, tab_map = st.tabs(
        ["Insights", "Trends", "Map"]
    )

    # ---------- INSIGHTS ----------
    with tab_insight:
        for _, row in df.iterrows():
            st.markdown(f"""
### {row['Country']}
- Population: **{format_compact(row['Population'])}**
- GDP per capita: **{format_compact(row['GDP per Capita'])} USD**
- Inequality (Gini): **{row['Gini Index'] if row['Gini Index'] else 'N/A'}**
- Growth signal: **{growth_badge(row['GDP per Capita'] / 10000 if row['GDP per Capita'] else None)}**

[History](https://en.wikipedia.org/wiki/History_of_{row['Country'].replace(' ', '_')})
            """)

    # ---------- TRENDS ----------
    with tab_trends:
        TREND_INDICATORS = {
            "Population": "SP.POP.TOTL",
            "GDP per Capita": "NY.GDP.PCAP.CD",
        }

        trend_label = st.selectbox("Indicator", list(TREND_INDICATORS.keys()))
        trend_metric = TREND_INDICATORS[trend_label]

        indexed = st.checkbox(
            "Index values (100 = first year)",
            value=(story != "None")
        )

        fig = go.Figure()
        has_data = False

        for name in selected:
            series = get_time_series(countries[name], trend_metric)
            if indexed:
                series = index_series(series)
            if len(series) < 2:
                continue

            fig.add_trace(go.Scatter(
                x=[y for y, _ in series],
                y=[v for _, v in series],
                mode="lines",
                name=name,
            ))
            has_data = True

        if has_data:
            fig.update_layout(
                title=f"{trend_label} – Historical trend",
                yaxis_title="Index (100 = base)" if indexed else trend_label,
                hovermode="x unified",
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.warning("No historical data available.")

    # ---------- MAP ----------
    with tab_map:
        MAP_INDICATORS = {
            "Population": "SP.POP.TOTL",
            "GDP per Capita": "NY.GDP.PCAP.CD",
        }

        map_label = st.selectbox("Map metric", list(MAP_INDICATORS.keys()))
        map_metric = MAP_INDICATORS[map_label]

        locations, values = [], []
        for name, code in countries.items():
            val = get_indicator(code, map_metric)
            locations.append(code)
            values.append(val if val is not None else float("nan"))

        selected_codes = [countries[c] for c in selected]

        fig = go.Figure()

        fig.add_trace(go.Choropleth(
            locations=locations,
            z=values,
            locationmode="ISO-3",
            colorscale="Viridis",
            colorbar_title=map_label,
            marker_line_color="white",
            marker_line_width=0.4,
        ))

        fig.add_trace(go.Choropleth(
            locations=[c for c in locations if c in selected_codes],
            z=[v for c, v in zip(locations, values) if c in selected_codes],
            locationmode="ISO-3",
            colorscale="Viridis",
            marker_line_color="black",
            marker_line_width=2.5,
            showscale=False,
        ))

        fig.update_layout(
            title=f"World Map – {map_label}",
            geo=dict(
                showframe=False,
                showcoastlines=True,
                showcountries=True,
                showland=True,
                landcolor="rgb(240,240,240)",
            ),
        )

        st.plotly_chart(fig, width="stretch")

st.caption("Built with Streamlit • Data source: World Bank")
