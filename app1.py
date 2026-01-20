
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
# MODE SWITCH
# ==================================================
mode = st.sidebar.radio(
    "Dashboard mode",
    ["-- Live (Population only)", "- Static (Full analysis)"]
)

# Auto-refresh ONLY in live mode
if mode.startswith("--"):
    st_autorefresh(interval=5_000, key="refresh")

# ==================================================
# Helpers
# ==================================================
def format_compact(n):
    if n is None:
        return "N/A"
    if n >= 1e12:
        return f"{n/1e12:.1f}T"
    elif n >= 1e9:
        return f"{n/1e9:.1f}B"
    elif n >= 1e6:
        return f"{n/1e6:.1f}M"
    elif n >= 1e3:
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
def get_all_populations(countries_dict):
    return {name: get_indicator(code, "SP.POP.TOTL") for name, code in countries_dict.items()}

# ==================================================
# Sidebar controls
# ==================================================
countries = get_countries()

selected_names = st.sidebar.multiselect(
    "Select countries",
    list(countries.keys()),
    default=["World", "United States", "India", "China"],
    max_selections=5,
)

# ==================================================
# LIVE MODE (Population only)
# ==================================================
if mode.startswith("--"):
    st.subheader("-- Live population comparison (estimated)")

    all_pops = get_all_populations(countries)
    world_pop = all_pops["World"]

    GLOBAL_BIRTHS = 140_000_000
    GLOBAL_DEATHS = 60_000_000
    SECONDS_PER_YEAR = 365 * 24 * 3600

    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    elapsed = time.time() - st.session_state.start_time

    values = []
    for name in selected_names:
        pop = all_pops.get(name)
        if pop:
            growth = (GLOBAL_BIRTHS - GLOBAL_DEATHS) * (pop / world_pop)
            values.append(growth / SECONDS_PER_YEAR * elapsed)
        else:
            values.append(0)

    fig = go.Figure(
        go.Bar(
            x=selected_names,
            y=values,
            text=[format_compact(v) for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Estimated population growth since page load",
        yaxis_range=[0, max(values) * 1.3 if values else 1],
        showlegend=False,
    )

    st.plotly_chart(fig, width="stretch")

    st.caption("-- Live mode updates every 5 seconds. Values are estimates.")

# ==================================================
# STATIC MODE (Full analysis)
# ==================================================
else:
    st.subheader("- Static country analysis")

    INDICATORS = {
        "Population": "SP.POP.TOTL",
        "GDP": "NY.GDP.MKTP.CD",
        "GDP per Capita": "NY.GDP.PCAP.CD",
        "Tax % GDP": "GC.TAX.TOTL.GD.ZS",
        "Gini Index": "SI.POV.GINI",
        "Literacy Rate %": "SE.ADT.LITR.ZS",
    }

    data = {}
    for name in selected_names:
        code = countries[name]
        data[name] = {}
        for label, ind in INDICATORS.items():
            try:
                data[name][label] = get_indicator(code, ind)
            except:
                data[name][label] = None

    df = pd.DataFrame.from_dict(data, orient="index").reset_index()
    df.rename(columns={"index": "Country"}, inplace=True)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Demographics", "Economy", "Inequality", "Map"]
    )

    with tab1:
        st.plotly_chart(
            go.Figure(
                go.Bar(
                    x=df["Country"],
                    y=df["Population"],
                    text=[format_compact(v) for v in df["Population"]],
                    textposition="outside",
                )
            ).update_layout(
                title="Population",
                yaxis_range=[0, df["Population"].max() * 1.2],
                showlegend=False,
            ),
            width="stretch",
        )

    with tab2:
        st.plotly_chart(
            go.Figure(
                go.Bar(
                    x=df["Country"],
                    y=df["GDP"],
                    text=[format_compact(v) for v in df["GDP"]],
                    textposition="outside",
                )
            ).update_layout(
                title="GDP (current USD)",
                yaxis_range=[0, df["GDP"].max() * 1.2],
                showlegend=False,
            ),
            width="stretch",
        )

    with tab3:
        st.plotly_chart(
            go.Figure(
                go.Bar(
                    x=df["Country"],
                    y=df["Gini Index"],
                    text=[f"{v:.1f}" if v else "N/A" for v in df["Gini Index"]],
                    textposition="outside",
                )
            ).update_layout(
                title="Income Inequality (Gini Index)",
                yaxis_range=[0, df["Gini Index"].max() * 1.2],
                showlegend=False,
            ),
            width="stretch",
        )

    with tab4:
      st.subheader("Time Series Trends")

    trend_metric = st.selectbox(
        "Select indicator",
        list(TREND_INDICATORS.keys()),
    )

    start_year, end_year = st.slider(
        "Year range",
        min_value=1960,
        max_value=datetime.now().year,
        value=(1990, datetime.now().year),
    )

    fig_trend = go.Figure()

    for name in selected_names:
        code = countries[name]
        series = get_time_series(code, TREND_INDICATORS[trend_metric], start_year)

        years = [y for y, v in series if y <= end_year]
        values = [v for y, v in series if y <= end_year]

        if values:
            fig_trend.add_trace(
                go.Scatter(
                    x=years,
                    y=values,
                    mode="lines+markers",
                    name=name,
                )
            )

    fig_trend.update_layout(
        title=f"{trend_metric} over time",
        xaxis_title="Year",
        yaxis_title=trend_metric,
        hovermode="x unified",
    )

    st.plotly_chart(fig_trend, width="stretch")

    st.caption(
        "Time series are annual World Bank values. "
        "Some indicators may have missing years."
    )


    st.download_button(
        "Download comparison table (CSV)",
        df.to_csv(index=False),
        file_name="country_comparison.csv",
        mime="text/csv",
    )

    with st.expander("Methodology"):
        st.markdown("""
        - Data source: World Bank
        - Live mode uses estimated growth rates
        - Static mode uses latest available yearly data
        - GDP per capita is an income proxy
        """)

# ==================================================
# Footer
# ==================================================
st.caption("Built with Streamlit • Data from World Bank")
