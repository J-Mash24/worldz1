
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
    "Central Europe": ["Poland","Hungary","Czech Republic","Slovakia","Romania","Ukraine","Bulgaria"],
    "EU": ["Austria", "Belgium", "Bulgaria", "Croatia", "Republic of Cyprus", "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"],
    "BRICS": ["Brazil","Russia","India","China","South Africa"],
    "The Caucasus": ["Russia", "Georgia", "Azerbaijan", "Armenia", "Turkey", "Iran"],
    "South Caucasus": ["Kazakhstan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Uzbekistan"],
    "Middle East": ["Saudi Arabia","United Arab Emirates","Qatar","Oman", "Israel","Syria", "Lebanon", "Jordan"],
    "South Asia": ["Afghanistan", "Bangladesh", "Bhutan", "India", "Maldives", "Nepal", "Pakistan", "Sri Lanka"],
    "East Asia": ["China","Japan","South Korea"],
    "West Africa": ["Benin", "Burkina Faso", "Cape Verde", "Côte d'Ivoire", "The Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Liberia", "Mali", "Mauritania", "Niger", "Nigeria", "Senegal", "Sierra Leone", "Togo"],
    "Central Africa": ["Angola", "Cameroon", "Central African Republic", "Chad", "Republic of the Congo", "Democratic Republic of the Congo", "Equatorial Guinea", "Gabon","São Tomé and Príncipe"],
    "Eastern Africa": ["Algeria", "Egypt", "Libya", "Morocco", "Tunisia"],
    "Southern Africa": ["Botswana", "Eswatini", "Lesotho", "Madagascar", "Malawi", "Mauritius", "Mozambique", "Namibia", "South Africa", "Zambia", "Zimbabwe"],
    "Central America": ["Belize", "Costa Rica", "El Salvador", "Guatemala", "Honduras", "Nicaragua", "Panama"],
    "South America": ["Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador", "Guyana", "Paraguay", "Peru", "Suriname", "Uruguay", "Venezuela"],
    "North America": ["Canada", "United States", "Mexico"],
    "The Carribean": ["Bahamas", "Barbados", "Cuba", "Dominican Republic", "Haiti", "Jamaica", "Saint Lucia", "Saint Vincent and the Grenadines"],
    "Oceania": ["Australia", "Fiji", "Kiribati", "Marshall Islands", "Micronesia", "Nauru", "New Zealand", "Palau", "Papua New Guinea", "Samoa", "Solomon Islands", "Tonga", "Tuvalu", "Vanuatu"]

}

REGION_INFO = {
    "Baltic States": "Modern, high-income, market-oriented economies, characterized by post-Soviet transition, strong EU integration, liberal policies, and a focus on attracting investment, with each country showing unique strengths like Estonia's tech (e-solutions), Lithuania's industry/innovation, and Latvia's transport/logistics, all interconnected and competitive within the EU single market.",
    "Central Europe": "Characterized by transition to market economies, integration into the EU, growth in tech/services, skilled labor, and ongoing development, with Czechia and Slovakia often seen as most advanced within the Visegrád Group (V4). They are key emerging markets with growing digital ecosystems, skilled workforces, and significant EU funding, but face challenges like youth emigration and regional disparities.",
    "Western Europe": "Advanced, capitalist systems with strong social welfare, high GDP, and significant service/tech sectors, evolving from post-WWII reconstruction (Marshall Plan) and Keynesian policies into integrated markets (EU) emphasizing free movement, trade, and robust welfare states, characterized by high living standards and financial hubs like London & Frankfurt.",
    "Southern Europe": "Characterized by strong service sectors (especially tourism), significant agriculture (olives, wine), historical industrial centers, and recent reforms boosting flexibility, but also regional disparities (e.g., North vs. South Italy) and reliance on FDI, balancing tradition with modern growth in renewables, tech, and manufacturing.",
    "Scandinavia": "Mixed-market systems blending free-market capitalism with extensive socialist-style welfare states, characterized by high living standards, strong social safety nets (universal healthcare, education), low income inequality, high labor participation (especially women), and strong unions, funded by high taxes and supporting competitive private enterprise alongside public services.",
    "Balkans": "Diverse, transitionary, often hierarchical market systems characterized by significant service sectors, growing digitalization, and varying development levels, shifting from agriculture to services/industry, with large economies like Romania/Greece/Bulgaria leading but facing shared challenges like regional disparities and post-conflict recovery, integrating more into global markets but retaining unique 'Balkan capitalism' traits",
    "Benelux": "The integrated economic union of Belgium, the Netherlands, and Luxembourg, forming a closely linked politico-economic bloc that promotes free movement of people, goods, services, and capital, acting as a pioneering model for wider European integration with shared policies on trade, development, and justice, fostering strong cross-border trade and logistical advantages.",
    "EU": "A diverse group of 27 nations forming a powerful single market, characterized by free movement of goods, services, capital, and people, operating under advanced mixed economies that blend free-market principles with social welfare, aiming for growth, stability, and cohesion through coordinated policies and institutions like the Eurozone and European Central Bank (ECB).",
    "BRICS": "Major emerging markets of Brazil, Russia, India, China, and South Africa, an influential bloc formed to promote economic cooperation, balance Western dominance in global governance, and increase their collective global power and influence through coordinated development and trade, representing significant shares of world GDP and population.",
    "The Caucasus": "A diverse, resource-rich but developing region between the Black and Caspian Seas, characterized by significant oil/gas, mining, agriculture (North Caucasus), and transit potential, yet challenged by weak regional integration, governance issues, reliance on commodities, informal economies, and unresolved conflicts, with a push towards diversification and private sector growth.",
    "South Caucasus": "A transition economy bridging Europe and Asia, characterized by resource wealth (oil/gas in Azerbaijan, mining in Armenia) and strategic transport corridors, but also high vulnerability, lack of diversification, reliance on remittances, political instability, and corruption, pushing for market reforms despite uneven growth and geopolitical risks.",
    "Middle East":"Largely defined by immense oil and gas wealth in some nations (like the Gulf states) that fuels high income, contrasting with resource-poor countries (like Jordan, Yemen) facing greater challenges, while others (like Israel, UAE) diversify into technology, finance, and services, all facing common issues like conflict, youth unemployment, and the need to move beyond hydrocarbon dependence.",
    "South Asia": "South Asia economies are diverse, emerging markets characterized by large populations, rapid growth (led by India, Pakistan, Bangladesh), heavy reliance on agriculture historically (though shifting to services like India's booming IT sector), and varying development levels, with India being a major global player while others like Sri Lanka & Bangladesh show strong growth; the region focuses on regional cooperation (SASEC) for connectivity, trade, and development despite significant poverty and infrastructure gaps.",
    "East Asia": "Dynamic, often high-growth economies of countries like Japan, China, South Korea, Taiwan, and Hong Kong, known for rapid industrialization, strong export-driven growth, technological innovation (especially in electronics/semiconductors), and significant global trade, emerging from post-war development into major world players. They are characterized by diverse systems, from Japan's free-market capitalism to China's socialist market model, yet share a focus on manufacturing, technology, high investment in education, and successful integration into the global economy.",
    "West Africa": "Diverse, resource-rich systems, largely unified by the Economic Community of West African States (ECOWAS), focused on promoting regional integration, trade, and development through cooperation in sectors like energy, agriculture, transport, and finance, while balancing significant natural resources (gold, oil, cocoa) with challenges in industrialization and infrastructure. Key features include reliance on commodities, burgeoning service sectors, efforts to build a common market (free trade, common currency), and varying levels of economic stability.",
    "Central Africa": "Often grouped under bodies like CEMAC or ECCAS, are generally characterized by rich natural resources (timber, oil, minerals), reliance on subsistence agriculture, forestry, and mining, but face significant challenges like landlocked geography, poor infrastructure, political instability, and poverty, leading to low growth and vulnerability to external shocks. Key sectors include agriculture, forestry (timber), and mineral extraction (diamonds, gold, oil), while regional integration aims to foster cooperation through common markets and infrastructure.",
    "Eastern Africa": "Diverse, fast-growing, resource-rich regions focused on agriculture, burgeoning services (ICT, finance, tourism), and infrastructure development, driven by the East African Community (EAC) and AfCFTA, aiming for integration through sectors like digital tech, energy, and manufacturing, despite challenges like poverty and inequality. They are becoming global growth leaders with significant potential in digital payments (M-PESA) and mobile tech, alongside traditional exports like coffee and tea, with major hubs in Nairobi and Addis Ababa.",
    "Southern Africa": "Often characterized by the Southern African Development Community (SADC), are diverse, mineral-rich, and deeply integrated through trade, but with significant disparities; they feature South Africa as the region's industrial powerhouse (driven by mining, finance, manufacturing) and include developing nations reliant on resources like minerals (Botswana, Namibia), agriculture, and increasingly, regional cooperation for sustainable growth, facing challenges like climate change and infrastructure gaps.",
    "Central America": "A developing, mixed economy characterized by traditional agriculture (coffee, bananas), growing manufacturing (textiles, food processing), and significant service sectors, especially in trade/tourism (Panama Canal), with heavy reliance on the U.S. market via CAFTA-DR but struggling with poverty and inequality, despite efforts towards regional integration.",
    "South America": "Characterized by rich natural resources, making it a major exporter of primary commodities like minerals (copper, gold, oil) and agricultural products (soy, coffee, sugar), but this reliance on global commodity prices creates vulnerability to 'booms and busts' and hinders diversification, with significant efforts focused on regional integration (like Mercosur), infrastructure, and boosting innovation and technology to overcome structural challenges and achieve sustainable, inclusive growth.",
    "North America": "A vast, diverse, resource-rich system encompassing Canada, the U.S., Mexico, Central America, and the Caribbean, characterized by highly developed sectors in the north (tech, finance) and developing ones in the south, with deep integration through trade (like the USMCA), abundant natural resources, and significant technological advancement, forming a major global economic bloc generating a large share of world GDP",
    "The Carribean": "Characterized by small, tourism-dependent, and open island economies heavily reliant on natural resources, agriculture, and services, facing challenges like import dependence, vulnerability to climate shocks (hurricanes), high debt, and the need for diversification beyond sugar, bauxite, and oil into areas like financial services, tech, and renewable energy for sustainable growth.",
    "Oceania": " Highly diverse, featuring Australia and New Zealand's advanced, mixed economies (driven by services, mining, tech) alongside the developing economies of smaller Pacific islands reliant on agriculture, fishing, and tourism, with some relying heavily on foreign aid. Key sectors include minerals/energy (Aus), dairy/agri/IT (NZ), and tourism/fisheries (islands), with significant trade links to Asia and the US, but challenges exist in sustainability, isolation, and climate change impacts."


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
    
         # Economy & society
        "Population": "SP.POP.TOTL",
        "GDP": "NY.GDP.MKTP.CD",
        "GDP per Capita": "NY.GDP.PCAP.CD",
        "Gini Index": "SI.POV.GINI",

    # Trade
        "Imports (USD)": "NE.IMP.GNFS.CD",
        "Exports (USD)": "NE.EXP.GNFS.CD",

    # Military
        "Military Spending (USD)": "MS.MIL.XPND.CD",
        "Military Spending (% GDP)": "MS.MIL.XPND.GD.ZS",
        "Armed Forces Personnel": "MS.MIL.TOTL.P1",
}


    tab_compare, tab_trends, tab_military, tab_trade, tab_map = st.tabs(
    ["Comparison", "Trends", "Military", "Trade", "Map"]
)


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

    with tab_military:
        st.subheader("Military capacity comparison")

    metric_label = st.selectbox(
        "Military metric",
        [
            "Military Spending (USD)",
            "Military Spending (% GDP)",
            "Armed Forces Personnel",
        ],
    )

    metric = INDICATORS[metric_label]

    labels, values = [], []

    for label, members in groups.items():
        vals, gdp_vals = [], []

        for c in members:
            code = countries.get(c)
            if not code:
                continue

            v = get_indicator(code, metric)
            gdp = get_indicator(code, "NY.GDP.MKTP.CD")

            if v is not None:
                vals.append(v)
                if gdp:
                    gdp_vals.append(gdp)

        if not vals:
            agg = None
        elif "USD" in metric_label or "Personnel" in metric_label:
            agg = sum(vals)
        else:
            # % GDP → GDP-weighted
            agg = sum(v * g for v, g in zip(vals, gdp_vals)) / sum(gdp_vals) if gdp_vals else None

        labels.append(label)
        values.append(agg)

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        text=[format_compact(v) for v in values],
        textposition="outside",
    ))

    fig.update_layout(
        title=metric_label,
        yaxis=dict(autorange=True),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Source: World Bank. Military indicators are proxies for capacity, not combat effectiveness."
    )


    with tab_trade:
      st.subheader("Trade comparison")

    trade_view = st.radio(
        "View",
        ["Imports", "Exports", "Trade Balance"],
        horizontal=True,
    )

    labels, values = [], []

    for label, members in groups.items():
        imports, exports = [], []

        for c in members:
            code = countries.get(c)
            if not code:
                continue

            imp = get_indicator(code, "NE.IMP.GNFS.CD")
            exp = get_indicator(code, "NE.EXP.GNFS.CD")

            if imp:
                imports.append(imp)
            if exp:
                exports.append(exp)

        if trade_view == "Imports":
            agg = sum(imports) if imports else None
        elif trade_view == "Exports":
            agg = sum(exports) if exports else None
        else:
            agg = (sum(exports) - sum(imports)) if imports or exports else None

        labels.append(label)
        values.append(agg)

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        text=[format_compact(v) for v in values],
        textposition="outside",
    ))

    fig.update_layout(
        title=f"{trade_view} (USD)",
        yaxis=dict(autorange=True),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Positive trade balance indicates net exporter; negative indicates net importer."
    )


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
