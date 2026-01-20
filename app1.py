
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
st.caption("Population, economy, tax structure, inequality, and education (World Bank data)")

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
st.sidebar.header("Controls")

countries = get_countries()

selected_names = st.sidebar.multiselect(
    "Select countries",
    list(countries.keys()),
    default=["World", "United States", "India", "China"],
    max_selections=5,
)

map_metric = st.sidebar.selectbox(
    "Map metric",
    ["Population", "GDP", "GDP per Capita", "Gini Index"],
)

# ==================================================
# Data preparation
# ==================================================
all_pops = get_all_populations(countries)
world_pop = all_pops["World"]

# Economic indicators
INDICATORS = {
    "GDP": "NY.GDP.MKTP.CD",
    "GDP per Capita": "NY.GDP.PCAP.CD",
    "Tax % GDP": "GC.TAX.TOTL.GD.ZS",
    "Gini Index": "SI.POV.GINI",
    "Education Spending % GDP": "SE.XPD.TOTL.GD.ZS",
    "Literacy Rate %": "SE.ADT.LITR.ZS",
}

data = {}

for name in selected_names:
    code = countries[name]
    data[name] = {
        "Population": all_pops.get(name),
    }
    for label, ind in INDICATORS.items():
        try:
            data[name][label] = get_indicator(code, ind)
        except:
            data[name][label] = None

df = pd.DataFrame.from_dict(data, orient="index").reset_index()
df.rename(columns={"index": "Country"}, inplace=True)

# ==================================================
# Tabs
# ==================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [" Demographics", " Economy", " Tax", "Inequality & Education", "Map"]
)

# =========================
# TAB 1 — Demographics
# =========================
with tab1:
    fig_pop = go.Figure(
        go.Bar(
            x=df["Country"],
            y=df["Population"],
            text=[format_compact(v) for v in df["Population"]],
            textposition="outside",
        )
    )
    fig_pop.update_layout(
        title="Population",
        yaxis_range=[0, df["Population"].max() * 1.2],
        showlegend=False,
    )
    st.plotly_chart(fig_pop, width="stretch")

# =========================
# TAB 2 — Economy
# =========================
with tab2:
    col1, col2 = st.columns(2)

    with col1:
        fig_gdp = go.Figure(
            go.Bar(
                x=df["Country"],
                y=df["GDP"],
                text=[format_compact(v) for v in df["GDP"]],
                textposition="outside",
            )
        )
        fig_gdp.update_layout(
            title="GDP (current USD)",
            yaxis_range=[0, df["GDP"].max() * 1.2],
            showlegend=False,
        )
        st.plotly_chart(fig_gdp, width="stretch")

    with col2:
        fig_gdppc = go.Figure(
            go.Bar(
                x=df["Country"],
                y=df["GDP per Capita"],
                text=[format_compact(v) for v in df["GDP per Capita"]],
                textposition="outside",
            )
        )
        fig_gdppc.update_layout(
            title="Income Proxy (GDP per Capita)",
            yaxis_range=[0, df["GDP per Capita"].max() * 1.2],
            showlegend=False,
        )
        st.plotly_chart(fig_gdppc, width="stretch")

# =========================
# TAB 3 — Tax
# =========================
with tab3:
    fig_tax = go.Figure(
        go.Bar(
            x=df["Country"],
            y=df["Tax % GDP"],
            text=[f"{v:.1f}%" if v else "N/A" for v in df["Tax % GDP"]],
            textposition="outside",
        )
    )
    fig_tax.update_layout(
        title="Total Tax Revenue (% of GDP)",
        yaxis_range=[0, df["Tax % GDP"].max() * 1.3],
        showlegend=False,
    )
    st.plotly_chart(fig_tax, width="stretch")

# =========================
# TAB 4 — Inequality & Education
# =========================
with tab4:
    col1, col2 = st.columns(2)

    with col1:
        fig_gini = go.Figure(
            go.Bar(
                x=df["Country"],
                y=df["Gini Index"],
                text=[f"{v:.1f}" if v else "N/A" for v in df["Gini Index"]],
                textposition="outside",
            )
        )
        fig_gini.update_layout(
            title="Income Inequality (Gini Index)",
            yaxis_range=[0, df["Gini Index"].max() * 1.2],
            showlegend=False,
        )
        st.plotly_chart(fig_gini, width="stretch")

    with col2:
        fig_edu = go.Figure(
            go.Bar(
                x=df["Country"],
                y=df["Literacy Rate %"],
                text=[f"{v:.1f}%" if v else "N/A" for v in df["Literacy Rate %"]],
                textposition="outside",
            )
        )
        fig_edu.update_layout(
            title="Adult Literacy Rate (%)",
            yaxis_range=[0, 100],
            showlegend=False,
        )
        st.plotly_chart(fig_edu, width="stretch")

# =========================
# TAB 5 — Map
# =========================
with tab5:
    map_values = {}

    for name, code in countries.items():
        try:
            if map_metric == "Population":
                value = all_pops.get(name)

            elif map_metric == "GDP":
                value = get_indicator(code, "NY.GDP.MKTP.CD")

            elif map_metric == "GDP per Capita":
                value = get_indicator(code, "NY.GDP.PCAP.CD")

            elif map_metric == "Gini Index":
                value = get_indicator(code, "SI.POV.GINI")

            else:
                value = None

        except:
            value = None

        if value is not None:
            map_values[code] = value

    fig_map = go.Figure(
        go.Choropleth(
            locations=list(map_values.keys()),
            z=list(map_values.values()),
            locationmode="ISO-3",
            colorscale="Viridis",
            colorbar_title=map_metric,
            marker_line_color="white",
            marker_line_width=0.3,
        )
    )

    fig_map.update_layout(
        title=f"World Map – {map_metric}",
        geo=dict(
            showframe=False,
            showcoastlines=True,
            coastlinecolor="gray",
            projection_type="natural earth",
        ),
    )

    st.plotly_chart(fig_map, width="stretch")

selected_codes = [countries[name] for name in selected_names]

fig_map.update_traces(
    marker_line_width=[
        2 if code in selected_codes else 0.3
        for code in map_values.keys()
    ]
)


# =========================
# Download
# =========================
st.download_button(
    "Download comparison table (CSV)",
    df.to_csv(index=False),
    file_name="country_comparison.csv",
    mime="text/csv",
)

# ==================================================
# Footer
# ==================================================
with st.expander("Methodology & Notes"):
    st.markdown("""
    - Data source: World Bank (latest available year)
    - GDP per capita is used as an income proxy
    - Tax values represent total government tax revenue (% of GDP)
    - Gini index measures income inequality (higher = more unequal)
    - Education metrics may be missing for some countries
    """)

st.caption("This dashboard shows official and estimated indicators. Interpret values accordingly.")
