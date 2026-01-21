

import time
import math
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ==================================================
# PAGE SETUP
# ==================================================
st.set_page_config(layout="wide")
st.title("Global Country & Region Comparison Dashboard")

# ==================================================
# SAFE HELPERS
# ==================================================
def safe_json(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

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

# ==================================================
# WORLD BANK API
# ==================================================
@st.cache_data
def get_countries():
    js = safe_json("https://api.worldbank.org/v2/country?format=json&per_page=400")
    if not js or len(js) < 2:
        return {}
    return {
        c["name"]: c["id"]
        for c in js[1]
        if c["region"]["id"] != "NA"
    }

@st.cache_data
def get_indicator(code, indicator):
    js = safe_json(
        f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json"
    )
    if not js or len(js) < 2 or js[1] is None:
        return None
    for d in js[1]:
        if d.get("value") is not None:
            return d["value"]
    return None

@st.cache_data
def get_series(code, indicator):
    js = safe_json(
        f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json&per_page=1000"
    )
    if not js or len(js) < 2 or js[1] is None:
        return []
    out = []
    for d in js[1]:
        if d["value"] is not None:
            out.append((int(d["date"]), d["value"]))
    return sorted(out)

# ==================================================
# REGIONS & BLOCS (WITH EXPLANATIONS)
# ==================================================
REGIONS = {
    "Europe": {
        "Benelux": {
            "countries": ["Belgium", "Netherlands", "Luxembourg"],
            "desc": "Highly integrated Western European economies with strong trade and EU coordination."
        },
        "Baltic States": {
            "countries": ["Estonia", "Latvia", "Lithuania"],
            "desc": "Post-Soviet EU members with rapid digital and economic convergence."
        },
        "Scandinavian Countries": {
            "countries": ["Sweden", "Norway", "Denmark", "Finland"],
            "desc": "Nordic welfare states with high social spending and low inequality."
        },
    },
    "Asia": {
        "East Asia": {
            "countries": ["China", "Japan", "South Korea"],
            "desc": "Export-oriented industrial economies with strong state coordination."
        },
        "Gulf Kingdoms": {
            "countries": ["Saudi Arabia", "United Arab Emirates", "Qatar", "Oman"],
            "desc": "Oil-rich monarchies with high GDP per capita and low taxation."
        },
    },
    "Africa": {
        "West Africa": {
            "countries": ["Nigeria", "Ghana", "Senegal"],
            "desc": "Fast-growing populations and emerging regional trade hubs."
        },
    },
    "Blocs": {
        "EU": {
            "countries": ["Germany", "France", "Italy", "Spain", "Poland"],
            "desc": "Highly integrated political and economic union."
        },
        "BRICS": {
            "countries": ["Brazil", "Russia", "India", "China", "South Africa"],
            "desc": "Large emerging economies with increasing global influence."
        },
    },
}

# ==================================================
# SIDEBAR CONTROLS
# ==================================================
countries = get_countries()

st.sidebar.header("Controls")

mode = st.sidebar.radio("Mode", ["Live", "Static"])

if mode == "Live":
    st_autorefresh(interval=5000, key="refresh")

selection_mode = st.sidebar.radio(
    "Compare",
    ["Manual (Countries)", "By Region / Bloc"]
)

groups = {}

if selection_mode == "Manual (Countries)":
    selected = st.sidebar.multiselect(
        "Countries",
        list(countries.keys()),
        ["United States", "China", "Germany"],
        max_selections=5,
    )
    groups = {"Selected countries": selected}

else:
    cont = st.sidebar.selectbox("Region", list(REGIONS.keys()))
    sub = st.sidebar.selectbox("Sub-region / Bloc", list(REGIONS[cont].keys()))

    info = REGIONS[cont][sub]
    groups = {sub: info["countries"]}

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### ℹ️ {sub}")
    st.sidebar.caption(info["desc"])
    st.sidebar.markdown("**Countries included:**")
    st.sidebar.write(", ".join(info["countries"]))

# ==================================================
# LIVE MODE
# ==================================================
if mode == "Live":
    st.subheader("Live Population Growth (Estimated)")

    GLOBAL_BIRTHS = 140_000_000
    GLOBAL_DEATHS = 60_000_000
    SECONDS_PER_YEAR = 365 * 24 * 3600

    if "start" not in st.session_state:
        st.session_state.start = time.time()

    elapsed = time.time() - st.session_state.start
    world_pop = get_indicator("WLD", "SP.POP.TOTL")

    labels, values = [], []

    for group, members in groups.items():
        total = 0
        for c in members:
            code = countries.get(c)
            if not code:
                continue
            pop = get_indicator(code, "SP.POP.TOTL")
            if pop and world_pop:
                total += (GLOBAL_BIRTHS - GLOBAL_DEATHS) * (pop / world_pop)

        labels.append(group)
        values.append(total / SECONDS_PER_YEAR * elapsed if total else 0)

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        text=[format_compact(v) for v in values],
        textposition="outside"
    ))

    fig.update_layout(title="Estimated growth since page load")
    st.plotly_chart(fig, use_container_width=True)

# ==================================================
# STATIC MODE
# ==================================================
else:
    INDICATORS = {
        "Population": "SP.POP.TOTL",
        "GDP per Capita": "NY.GDP.PCAP.CD",
    }

    tab_compare, tab_trends, tab_map = st.tabs(
        ["Comparison", "Trends", "Map"]
    )

    # ---------- COMPARISON ----------
    with tab_compare:
        metric_label = st.selectbox("Metric", list(INDICATORS.keys()))
        metric = INDICATORS[metric_label]

        labels, values = [], []

        for group, members in groups.items():
            vals = []
            for c in members:
                code = countries.get(c)
                if code:
                    v = get_indicator(code, metric)
                    if v:
                        vals.append(v)
            labels.append(group)
            values.append(sum(vals) / len(vals) if vals else None)

        fig = go.Figure(go.Bar(
            x=labels,
            y=values,
            text=[format_compact(v) for v in values],
            textposition="outside"
        ))
        fig.update_layout(title=f"{metric_label} comparison")
        st.plotly_chart(fig, use_container_width=True)

    # ---------- TRENDS ----------
    with tab_trends:
        fig = go.Figure()
        for group, members in groups.items():
            series_sum = {}
            count = 0
            for c in members:
                code = countries.get(c)
                for y, v in get_series(code, "SP.POP.TOTL"):
                    series_sum[y] = series_sum.get(y, 0) + v
                count += 1
            if series_sum:
                fig.add_trace(go.Scatter(
                    x=list(series_sum.keys()),
                    y=[v / count for v in series_sum.values()],
                    mode="lines",
                    name=group
                ))

        fig.update_layout(title="Population trends (average)")
        st.plotly_chart(fig, use_container_width=True)

    # ---------- MAP ----------
    with tab_map:
        map_vals = []
        locs = []

        for name, code in countries.items():
            v = get_indicator(code, "SP.POP.TOTL")
            locs.append(code)
            map_vals.append(v if v else float("nan"))

        fig = go.Figure(go.Choropleth(
            locations=locs,
            z=map_vals,
            locationmode="ISO-3",
            colorscale="Viridis",
            marker_line_color="white",
            marker_line_width=0.4,
        ))

        # Highlight selected
        sel_codes = {countries[c] for g in groups.values() for c in g if c in countries}
        fig.add_trace(go.Choropleth(
            locations=list(sel_codes),
            z=[1] * len(sel_codes),
            locationmode="ISO-3",
            showscale=False,
            marker_line_color="black",
            marker_line_width=2.5,
        ))

        fig.update_layout(
            title="World Map",
            geo=dict(showframe=False, showcoastlines=True, showcountries=True)
        )
        st.plotly_chart(fig, use_container_width=True)

st.caption("Built with Streamlit • Data: World Bank")
