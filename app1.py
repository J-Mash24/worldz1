
import time
import math
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ==================================================
# PAGE
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
    for v, s in [(1e12,"T"),(1e9,"B"),(1e6,"M"),(1e3,"K")]:
        if n >= v:
            return f"{n/v:.1f}{s}"
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
    return sorted(
        [(int(d["date"]), d["value"]) for d in js[1] if d.get("value") is not None]
    )

# ==================================================
# REGIONS & BLOCS (EXPANDED)
# ==================================================
REGIONS = {
    "Western Europe": ["Germany","France","Netherlands","Belgium","Austria","Switzerland"],
    "Benelux": ["Belgium","Netherlands","Luxembourg"],
    "Baltic States": ["Estonia","Latvia","Lithuania"],
    "Scandinavia": ["Sweden","Norway","Denmark","Finland", "Island"],
    "Southern Europe": ["Italy","Spain","Portugal","Greece"],
    "Balkans": ["Serbia","Croatia","Bosnia and Herzegovina","Albania","North Macedonia"],
    "Warsaw Pact (historic)": ["Poland","Hungary","Czech Republic","Slovakia","Romania","Bulgaria"],
    "East Asia": ["China","Japan","South Korea"],
    "South Asia": ["India","Pakistan","Bangladesh"],
    "Gulf Monarchies": ["Saudi Arabia","United Arab Emirates","Qatar","Oman","Kuwait"],
    "West Africa": ["Nigeria","Ghana","Senegal"],
    "Arab Spring": ["Egypt","Morocco","Tunisia"],
    "EU": ["A bunch of countries :)"],
    "BRICS": ["Brazil","Russia","India","China","South Africa"],
}

REGION_INFO = {
    "Benelux": "Highly integrated low-trade-barrier economies.",
    "Warsaw Pact (historic)": "Former socialist economies with shared institutional legacy.",
    "Balkans": "Post-Yugoslav and Southeast European transition economies.",
}

# ==================================================
# SIDEBAR
# ==================================================
countries = get_countries()

st.sidebar.header("Controls")

mode = st.sidebar.radio("Mode", ["Live", "Static"])
if mode == "Live":
    st_autorefresh(interval=5000, key="refresh")

selection_type = st.sidebar.radio(
    "Compare",
    ["Countries", "Regions / Blocs"]
)

if selection_type == "Countries":
    selected_items = st.sidebar.multiselect(
        "Select countries",
        list(countries.keys()),
        ["United States","China","Germany"],
        max_selections=6
    )
    groups = {c:[c] for c in selected_items}

else:
    selected_items = st.sidebar.multiselect(
        "Select regions / blocs",
        list(REGIONS.keys()),
        ["EU","BRICS"]
    )
    groups = {r:REGIONS[r] for r in selected_items}

# Sidebar explanations
for r in selected_items:
    if r in REGION_INFO:
        st.sidebar.caption(f"**{r}:** {REGION_INFO[r]}")
        st.sidebar.caption(", ".join(REGIONS[r]))

# ==================================================
# LIVE MODE
# ==================================================
if mode == "Live":
    st.subheader("Live Population Growth (Estimated)")

    GLOBAL_BIRTHS = 140_000_000
    GLOBAL_DEATHS = 60_000_000
    SECONDS_PER_YEAR = 365*24*3600

    if "start" not in st.session_state:
        st.session_state.start = time.time()

    elapsed = time.time() - st.session_state.start
    world_pop = get_indicator("WLD","SP.POP.TOTL")

    labels, values = [], []

    for label, members in groups.items():
        total = 0
        for c in members:
            pop = get_indicator(countries.get(c,""),"SP.POP.TOTL")
            if pop and world_pop:
                total += (GLOBAL_BIRTHS-GLOBAL_DEATHS)*(pop/world_pop)
        labels.append(label)
        values.append(total/SECONDS_PER_YEAR*elapsed if total else 0)

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        text=[format_compact(v) for v in values],
        textposition="outside"
    ))

    fig.update_layout(
        title="Estimated population increase since page load",
        yaxis=dict(autorange=True)
    )

    st.plotly_chart(fig, use_container_width=True)

# ==================================================
# STATIC MODE
# ==================================================
else:
    tab_compare, tab_trends, tab_map = st.tabs(
        ["Comparison","Trends","Map"]
    )

    INDICATORS = {
        "Population":"SP.POP.TOTL",
        "GDP":"NY.GDP.MKTP.CD",
        "GDP per Capita":"NY.GDP.PCAP.CD"
    }

    # -------- Comparison --------
    with tab_compare:
        metric_label = st.selectbox("Metric", INDICATORS.keys())
        metric = INDICATORS[metric_label]

        labels, values = [], []

        for label, members in groups.items():
            vals=[]
            for c in members:
                v = get_indicator(countries.get(c,""), metric)
                if v:
                    vals.append(v)
            labels.append(label)
            values.append(sum(vals)/len(vals) if vals else None)

        fig = go.Figure(go.Bar(
            x=labels,
            y=values,
            text=[format_compact(v) for v in values],
            textposition="outside"
        ))

        fig.update_layout(
            title=f"{metric_label} comparison",
            yaxis=dict(autorange=True)
        )

        st.plotly_chart(fig, use_container_width=True)

    # -------- Trends --------
    with tab_trends:
        trend_label = st.selectbox("Trend metric", INDICATORS.keys())
        metric = INDICATORS[trend_label]

        fig = go.Figure()

        for label, members in groups.items():
            yearly={}
            count=0
            for c in members:
                for y,v in get_series(countries.get(c,""),metric):
                    yearly[y]=yearly.get(y,0)+v
                count+=1
            if yearly:
                fig.add_trace(go.Scatter(
                    x=list(yearly.keys()),
                    y=[v/count for v in yearly.values()],
                    mode="lines",
                    name=label
                ))

        fig.update_layout(
            title=f"{trend_label} trends",
            hovermode="x unified"
        )

        st.plotly_chart(fig, use_container_width=True)

    # -------- Map --------
    with tab_map:
        vals, locs = [], []
        for name, code in countries.items():
            v = get_indicator(code,"SP.POP.TOTL")
            locs.append(code)
            vals.append(v if v else float("nan"))

        fig = go.Figure(go.Choropleth(
            locations=locs,
            z=vals,
            locationmode="ISO-3",
            colorscale="Viridis",
            marker_line_color="white",
            marker_line_width=0.4
        ))

        highlight = {countries[c] for g in groups.values() for c in g if c in countries}
        fig.add_trace(go.Choropleth(
            locations=list(highlight),
            z=[1]*len(highlight),
            locationmode="ISO-3",
            showscale=False,
            marker_line_color="black",
            marker_line_width=2.5
        ))

        fig.update_layout(
            title="World map",
            geo=dict(showframe=False, showcoastlines=True, showcountries=True)
        )

        st.plotly_chart(fig, use_container_width=True)

st.caption("Built with Streamlit • Data: World Bank")
