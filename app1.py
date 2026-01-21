
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
    "Balkans": ["Serbia","Croatia","Bosnia and Herzegovina","Albania","North Macedonia", "Slovenia"],
    "Warsaw Pact (historic)": ["Poland","Hungary","Czech Republic","Slovakia","Romania","Bulgaria"],
    "EU": ["A 27 countries coalition"],
    "BRICS": ["Brazil","Russia","India","China","South Africa"],
    "Middle East": ["Saudi Arabia","United Arab Emirates","Qatar","Oman", "Israel","Syria", "Lebanon", "Jordan"],
    "South Asia": ["Afghanistan", "Bangladesh", "Bhutan", "India", "Maldives", "Nepal", "Pakistan", "Sri Lanka"],
    "East Asia": ["China","Japan","South Korea"],
    "West Africa": ["Nigeria","Ghana","Senegal"],
    "Central Africa": ["Angola", "Cameroon", "Central African Republic", "Chad", "Republic of the Congo", "Democratic Republic of the Congo", "Equatorial Guinea", "Gabon","São Tomé and Príncipe"],
    "Eastern Africa": ["Algeria", "Egypt", "Libya", "Morocco", "Tunisia"],
    "Southern Africa": ["Botswana", "Eswatini", "Lesotho", "Madagascar", "Malawi", "Mauritius", "Mozambique", "Namibia", "South Africa", "Zambia", "Zimbabwe"],

}

REGION_INFO = {
    "Baltic States": "Modern, high-income, market-oriented economies, characterized by post-Soviet transition, strong EU integration, liberal policies, and a focus on attracting investment, with each country showing unique strengths like Estonia's tech (e-solutions), Lithuania's industry/innovation, and Latvia's transport/logistics, all interconnected and competitive within the EU single market.",
    "Warsaw Pact (historic)": "Characterized by transition to market economies, integration into the EU, growth in tech/services, skilled labor, and ongoing development, with Czechia and Slovakia often seen as most advanced within the Visegrád Group (V4). They are key emerging markets with growing digital ecosystems, skilled workforces, and significant EU funding, but face challenges like youth emigration and regional disparities.",
    "Western Europe": "Advanced, capitalist systems with strong social welfare, high GDP, and significant service/tech sectors, evolving from post-WWII reconstruction (Marshall Plan) and Keynesian policies into integrated markets (EU) emphasizing free movement, trade, and robust welfare states, characterized by high living standards and financial hubs like London & Frankfurt.",
    "Southern Europe": "Characterized by strong service sectors (especially tourism), significant agriculture (olives, wine), historical industrial centers, and recent reforms boosting flexibility, but also regional disparities (e.g., North vs. South Italy) and reliance on FDI, balancing tradition with modern growth in renewables, tech, and manufacturing.",
    "Scandinavia": "Mixed-market systems blending free-market capitalism with extensive socialist-style welfare states, characterized by high living standards, strong social safety nets (universal healthcare, education), low income inequality, high labor participation (especially women), and strong unions, funded by high taxes and supporting competitive private enterprise alongside public services.",
    "Balkans": "Diverse, transitionary, often hierarchical market systems characterized by significant service sectors, growing digitalization, and varying development levels, shifting from agriculture to services/industry, with large economies like Romania/Greece/Bulgaria leading but facing shared challenges like regional disparities and post-conflict recovery, integrating more into global markets but retaining unique 'Balkan capitalism' traits",
    "Benelux": "The integrated economic union of Belgium, the Netherlands, and Luxembourg, forming a closely linked politico-economic bloc that promotes free movement of people, goods, services, and capital, acting as a pioneering model for wider European integration with shared policies on trade, development, and justice, fostering strong cross-border trade and logistical advantages.",
    "EU": "A diverse group of 27 nations forming a powerful single market, characterized by free movement of goods, services, capital, and people, operating under advanced mixed economies that blend free-market principles with social welfare, aiming for growth, stability, and cohesion through coordinated policies and institutions like the Eurozone and European Central Bank (ECB).",
    "BRICS": "Major emerging markets of Brazil, Russia, India, China, and South Africa, an influential bloc formed to promote economic cooperation, balance Western dominance in global governance, and increase their collective global power and influence through coordinated development and trade, representing significant shares of world GDP and population.",
    "Middle East":"Largely defined by immense oil and gas wealth in some nations (like the Gulf states) that fuels high income, contrasting with resource-poor countries (like Jordan, Yemen) facing greater challenges, while others (like Israel, UAE) diversify into technology, finance, and services, all facing common issues like conflict, youth unemployment, and the need to move beyond hydrocarbon dependence.",
    "South Asia": "South Asia economies are diverse, emerging markets characterized by large populations, rapid growth (led by India, Pakistan, Bangladesh), heavy reliance on agriculture historically (though shifting to services like India's booming IT sector), and varying development levels, with India being a major global player while others like Sri Lanka & Bangladesh show strong growth; the region focuses on regional cooperation (SASEC) for connectivity, trade, and development despite significant poverty and infrastructure gaps.",
    "East Asia": "Dynamic, often high-growth economies of countries like Japan, China, South Korea, Taiwan, and Hong Kong, known for rapid industrialization, strong export-driven growth, technological innovation (especially in electronics/semiconductors), and significant global trade, emerging from post-war development into major world players. They are characterized by diverse systems, from Japan's free-market capitalism to China's socialist market model, yet share a focus on manufacturing, technology, high investment in education, and successful integration into the global economy.",
    "West Africa": "Diverse, resource-rich systems, largely unified by the Economic Community of West African States (ECOWAS), focused on promoting regional integration, trade, and development through cooperation in sectors like energy, agriculture, transport, and finance, while balancing significant natural resources (gold, oil, cocoa) with challenges in industrialization and infrastructure. Key features include reliance on commodities, burgeoning service sectors, efforts to build a common market (free trade, common currency), and varying levels of economic stability.",
    "Central Africa": "Often grouped under bodies like CEMAC or ECCAS, are generally characterized by rich natural resources (timber, oil, minerals), reliance on subsistence agriculture, forestry, and mining, but face significant challenges like landlocked geography, poor infrastructure, political instability, and poverty, leading to low growth and vulnerability to external shocks. Key sectors include agriculture, forestry (timber), and mineral extraction (diamonds, gold, oil), while regional integration aims to foster cooperation through common markets and infrastructure.",
    "Eastern Africa": "Diverse, fast-growing, resource-rich regions focused on agriculture, burgeoning services (ICT, finance, tourism), and infrastructure development, driven by the East African Community (EAC) and AfCFTA, aiming for integration through sectors like digital tech, energy, and manufacturing, despite challenges like poverty and inequality. They are becoming global growth leaders with significant potential in digital payments (M-PESA) and mobile tech, alongside traditional exports like coffee and tea, with major hubs in Nairobi and Addis Ababa.",
    "Southern Africa": "Often characterized by the Southern African Development Community (SADC), are diverse, mineral-rich, and deeply integrated through trade, but with significant disparities; they feature South Africa as the region's industrial powerhouse (driven by mining, finance, manufacturing) and include developing nations reliant on resources like minerals (Botswana, Namibia), agriculture, and increasingly, regional cooperation for sustainable growth, facing challenges like climate change and infrastructure gaps."


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
# LIVE MODE (FIXED)
# ==================================================
if mode == "Live":
    st.subheader("-- Live Population Growth (Estimated)")

    GLOBAL_BIRTHS = 140_000_000
    GLOBAL_DEATHS = 60_000_000
    SECONDS_PER_YEAR = 365 * 24 * 3600

    if "start_time" not in st.session_state:
        st.session_state.start_time = time.time()

    elapsed = time.time() - st.session_state.start_time
    world_pop = get_indicator("WLD", "SP.POP.TOTL")

    labels, values = [], []

    for label, members in groups.items():
        total_growth_per_year = 0

        for c in members:
            code = countries.get(c)
            pop = get_indicator(code, "SP.POP.TOTL")

            if pop and world_pop:
                total_growth_per_year += (
                    (GLOBAL_BIRTHS - GLOBAL_DEATHS) * (pop / world_pop)
                )

        labels.append(label)
        values.append(total_growth_per_year / SECONDS_PER_YEAR * elapsed)

    if not labels:
        st.info("Select countries or regions to see live data.")
    else:
        fig = go.Figure(go.Bar(
            x=labels,
            y=values,
            text=[format_compact(v) for v in values],
            textposition="outside",
        ))

        fig.update_layout(
            title="Estimated population increase since page load",
            yaxis=dict(autorange=True),
        )

        st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Live values are extrapolated from annual global demographic rates "
        "(not real-time census data)."
    )


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
