
import time
import requests
from datetime import datetime
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd

# ==================================================
# Page setup
# ==================================================
st.set_page_config(layout="wide")
st.title("Global Country Comparison Dashboard")

# ==================================================
# MODE SWITCH (CRITICAL)
# ==================================================
mode = st.sidebar.radio(
    "Dashboard mode",
    ["-- Live (Demographics)", "- Static (Full Analysis)"],
)

# Auto-refresh ONLY in live mode
if mode.startswith("--"):
    st_autorefresh(interval=5_000, key="refresh")

# ==================================================
# HELPERS
# ==================================================
def format_compact(n):
    if n is None:
        return "N/A"
    if n >= 1e12:
        return f"{n/1e12:.1f}T"
    if n >= 1e9:
        return f"{n/1e9:.1f}B"
    if n >= 1e6:
        return f"{n/1e6:.1f}M"
    if n >= 1e3:
        return f"{n/1e3:.1f}K"
    return str(int(n))

@st.cache_data
def get_countries():
    url = "https://api.worldbank.org/v2/country?format=json&per_page=400"
    data = requests.get(url, timeout=10).json()[1]
    countries = {c["name"]: c["id"] for c in data if c["region"]["id"] != "NA"}
    countries["World"] = "WLD"
    return dict(sorted(countries.items()))

@st.cache_data
def get_indicator(code, indicator):
    url = f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json"
    data = requests.get(url, timeout=10).json()
    latest = next(d for d in data[1] if d["value"] is not None)
    return latest["value"]

@st.cache_data
def get_time_series(code, indicator):
    url = f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json&per_page=1000"
    data = requests.get(url, timeout=10).json()[1]
    return sorted(
        [(int(d["date"]), d["value"]) for d in data if d["value"] is not None]
    )

# ==================================================
# SIDEBAR CONTROLS
# ==================================================
countries = get_countries()

selected = st.sidebar.multiselect(
    "Select countries",
    list(countries.keys()),
    ["World", "United States", "India"],
    max_selections=5,
)

# ==================================================
# 🔴 LIVE MODE — DEMOGRAPHICS ONLY
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
        growth = (GLOBAL_BIRTHS - GLOBAL_DEATHS) * (pop / world_pop)
        values.append(growth / SECONDS_PER_YEAR * elapsed)

    fig = go.Figure(
        go.Bar(
            x=selected,
            y=values,
            text=[format_compact(v) for v in values],
            textposition="outside",
        )
    )

    fig.update_layout(
        title="Estimated population increase since page load",
        yaxis_range=[0, max(values) * 1.3 if values else 1],
        showlegend=False,
    )

    st.plotly_chart(fig, width="stretch")

    st.caption("-- Live values are extrapolated from annual demographic rates.")

# ==================================================
# ⚪ STATIC MODE — FULL ANALYSIS
# ==================================================
else:
    st.subheader("- Static Country Analysis")

    INDICATORS = {
        "Population": "SP.POP.TOTL",
        "GDP": "NY.GDP.MKTP.CD",
        "GDP per Capita": "NY.GDP.PCAP.CD",
        "Tax % GDP": "GC.TAX.TOTL.GD.ZS",
        "Gini Index": "SI.POV.GINI",
        "Literacy Rate %": "SE.ADT.LITR.ZS",
    }

    rows = []
    for name in selected:
        code = countries[name]
        row = {"Country": name}
        for label, ind in INDICATORS.items():
            try:
                row[label] = get_indicator(code, ind)
            except:
                row[label] = None
        rows.append(row)

    df = pd.DataFrame(rows)

    # -------------------------
    # STATIC TABS
    # -------------------------
    tab_demo, tab_econ, tab_ineq, tab_trends, tab_map = st.tabs(
        ["Demographics", "Economy", "Inequality & Education", "Trends", "Map"]
    )

    # --- Demographics ---
    with tab_demo:
        fig = go.Figure(
            go.Bar(
                x=df["Country"],
                y=df["Population"],
                text=[format_compact(v) for v in df["Population"]],
                textposition="outside",
            )
        )
        fig.update_layout(
            title="Population",
            yaxis_range=[0, df["Population"].max() * 1.2],
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")

    # --- Economy ---
    with tab_econ:
        fig = go.Figure(
            go.Bar(
                x=df["Country"],
                y=df["GDP"],
                text=[format_compact(v) for v in df["GDP"]],
                textposition="outside",
            )
        )
        fig.update_layout(
            title="GDP (current USD)",
            yaxis_range=[0, df["GDP"].max() * 1.2],
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")

    # --- Inequality & Education ---
    with tab_ineq:
        col1, col2 = st.columns(2)

        with col1:
            fig = go.Figure(
                go.Bar(
                    x=df["Country"],
                    y=df["Gini Index"],
                    text=[f"{v:.1f}" if v else "N/A" for v in df["Gini Index"]],
                    textposition="outside",
                )
            )
            fig.update_layout(
                title="Income Inequality (Gini Index)",
                yaxis_range=[0, df["Gini Index"].max() * 1.2],
                showlegend=False,
            )
            st.plotly_chart(fig, width="stretch")

        with col2:
            fig = go.Figure(
                go.Bar(
                    x=df["Country"],
                    y=df["Literacy Rate %"],
                    text=[f"{v:.1f}%" if v else "N/A" for v in df["Literacy Rate %"]],
                    textposition="outside",
                )
            )
            fig.update_layout(
                title="Adult Literacy Rate (%)",
                yaxis_range=[0, 100],
                showlegend=False,
            )
            st.plotly_chart(fig, width="stretch")

    # --- Trends ---
    with tab_trends:
        metric = st.selectbox(
            "Indicator",
            {
                "Population": "SP.POP.TOTL",
                "GDP": "NY.GDP.MKTP.CD",
                "GDP per Capita": "NY.GDP.PCAP.CD",
            },
        )

        fig = go.Figure()
        for name in selected:
            series = get_time_series(countries[name], metric)
            years = [y for y, v in series]
            values = [v for y, v in series]
            fig.add_trace(go.Scatter(x=years, y=values, mode="lines", name=name))

        fig.update_layout(
            title="Historical trends",
            hovermode="x unified",
        )

        st.plotly_chart(fig, width="stretch")

    # --- Map ---
    with tab_map:
        map_metric = st.selectbox(
            "Map metric",
            {
                "Population": "SP.POP.TOTL",
                "GDP": "NY.GDP.MKTP.CD",
                "GDP per Capita": "NY.GDP.PCAP.CD",
                "Gini Index": "SI.POV.GINI",
            },
        )

        map_values = {
            code: get_indicator(code, map_metric)
            for _, code in countries.items()
        }

        fig = go.Figure(
            go.Choropleth(
                locations=list(map_values.keys()),
                z=list(map_values.values()),
                locationmode="ISO-3",
                colorscale="Viridis",
                colorbar_title=map_metric,
            )
        )

        fig.update_layout(
            title="World map",
            geo=dict(showframe=False, showcoastlines=True),
        )

        st.plotly_chart(fig, width="stretch")

    # --- Download ---
    st.download_button(
        "Download comparison table (CSV)",
        df.to_csv(index=False),
        "country_comparison.csv",
        "text/csv",
    )

    with st.expander("Methodology"):
        st.markdown("""
        - Data source: World Bank
        - Live values are extrapolated estimates
        - Static data shows latest available year
        - GDP per capita is an income proxy
        """)

st.caption("Built with Streamlit • Data from World Bank")
