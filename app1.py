
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
# HELPERS
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
# REGIONS & EXPLANATIONS
# ==================================================
REGIONS = {
    "Baltic States": ["Estonia","Latvia","Lithuania"],
    "Benelux": ["Belgium","Netherlands","Luxembourg"],
    "Scandinavia": ["Sweden","Norway","Denmark","Finland"],
    "Western Europe": ["Germany","France","Austria","Switzerland"],
    "Southern Europe": ["Italy","Spain","Portugal","Greece"],
    "Balkans": ["Serbia","Croatia","Bosnia and Herzegovina","Albania","North Macedonia"],
    "Warsaw Pact (historic)": ["Poland","Hungary","Czech Republic","Slovakia","Romania","Bulgaria"],
    "EU": ["Germany","France","Italy","Spain","Poland","Netherlands"],
    "BRICS": ["Brazil","Russia","India","China","South Africa"],
}

REGION_INFO = {
    "Baltic States": "Small open economies, strong EU integration, high digitalization.",
    "Warsaw Pact (historic)": "Former socialist economies with shared institutional legacy.",
    "Balkans": "Post-Yugoslav and Southeast European transition economies.",
    "Benelux": "Highly integrated, trade-driven Western European economies.",
}

# ==================================================
# SIDEBAR
# ==================================================
countries = get_countries()

st.sidebar.header("Controls")

mode = st.sidebar.radio("Mode", ["Live", "Static"])
if mode == "Live":
    st_autorefresh(interval=5000, key="refresh")

selection_type = st.sidebar.radio("Compare", ["Countries", "Regions / Blocs"])

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

# 🔹 Region explanation block
with st.sidebar.expander("Region definitions"):
    for r in selected_items:
        if r in REGIONS:
            st.markdown(f"**{r}**")
            if r in REGION_INFO:
                st.caption(REGION_INFO[r])
            st.caption(", ".join(REGIONS[r]))

# ==================================================
# STATIC MODE
# ==================================================
if mode == "Static":

    INDICATORS = {
        "Population": "SP.POP.TOTL",
        "GDP": "NY.GDP.MKTP.CD",
        "GDP per Capita": "NY.GDP.PCAP.CD",
        "Gini Index": "SI.POV.GINI",
    }

    tab_compare, tab_trends, tab_map = st.tabs(["Comparison","Trends","Map"])

    # ---------- COMPARISON ----------
    with tab_compare:
        metric_label = st.selectbox("Metric", INDICATORS.keys())
        metric = INDICATORS[metric_label]

        labels, values = [], []

        for label, members in groups.items():
            pops, vals = [], []

            for c in members:
                code = countries.get(c)
                v = get_indicator(code, metric)
                p = get_indicator(code, "SP.POP.TOTL")
                if v is not None:
                    vals.append(v)
                if p:
                    pops.append(p)

            if not vals:
                agg = None
            elif metric_label in ["Population", "GDP"]:
                agg = sum(vals)
            elif metric_label == "GDP per Capita":
                agg = sum(v*p for v,p in zip(vals,pops)) / sum(pops)
            else:  # Gini
                agg = sum(vals)/len(vals)

            labels.append(label)
            values.append(agg)

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

    # ---------- TRENDS ----------
    with tab_trends:
        trend_label = st.selectbox("Trend metric", INDICATORS.keys())
        metric = INDICATORS[trend_label]

        fig = go.Figure()

        for label, members in groups.items():
            yearly, yearly_pop = {}, {}

            for c in members:
                code = countries.get(c)
                for y,v in get_series(code, metric):
                    yearly[y] = yearly.get(y,0) + v
                for y,p in get_series(code, "SP.POP.TOTL"):
                    yearly_pop[y] = yearly_pop.get(y,0) + p

            if yearly:
                if trend_label == "GDP per Capita":
                    yvals = [yearly[y]/yearly_pop[y] for y in yearly if y in yearly_pop]
                    xvals = [y for y in yearly if y in yearly_pop]
                else:
                    xvals = list(yearly.keys())
                    yvals = list(yearly.values())

                fig.add_trace(go.Scatter(
                    x=xvals,
                    y=yvals,
                    mode="lines",
                    name=label
                ))

        fig.update_layout(
            title=f"{trend_label} trends",
            hovermode="x unified"
        )

        st.plotly_chart(fig, use_container_width=True)

    # ---------- MAP ----------
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
