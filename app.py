# app.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from typing import Tuple, Dict, List

st.set_page_config(page_title="Last-Mile Delivery Analytics", layout="wide")

# ---------- Utilities ----------
EXPECTED_COLS = ["Delivery_Time","Traffic","Weather","Vehicle","Agent_Age","Agent_Rating","Area","Category"]

@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl")
    # Flexible column mapping: try to normalize common header variants
    col_map = {c.lower().strip(): c for c in df.columns}
    rename = {}
    for need in EXPECTED_COLS:
        # try exact
        if need in df.columns:
            continue
        # try case-insensitive approximate
        hits = [orig for key, orig in col_map.items() if key.replace(" ", "_") == need.lower()]
        if not hits:
            # additional fuzzy keys
            aliases = {
                "delivery_time": ["delivery time","time","del_time","duration","mins","minutes"],
                "traffic": ["traffic_level","traffic_condition","traffic status","traffic status"],
                "weather": ["weather_condition","climate","met"],
                "vehicle": ["vehicle_type","mode","fleet","transport"],
                "agent_age": ["age","delivery_agent_age","courier_age"],
                "agent_rating": ["rating","delivery_agent_rating","courier_rating","score"],
                "area": ["region","zone","location"],
                "category": ["product_category","item_category","sku_category"]
            }
            key = need.lower()
            candidates = []
            for alias in aliases.get(key, []):
                for k, orig in col_map.items():
                    if alias.replace(" ", "_") == k:
                        candidates.append(orig)
            hits = candidates
        if hits:
            rename[hits[0]] = need
    if rename:
        df = df.rename(columns=rename)

    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

    # Clean types and labels
    for c in ["Traffic","Weather","Vehicle","Area","Category"]:
        df[c] = df[c].astype(str).str.strip().str.title()
    for c in ["Delivery_Time","Agent_Age","Agent_Rating"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Drop rows without essential metrics
    df = df.dropna(subset=["Delivery_Time"])
    return df

def derive_features(df: pd.DataFrame, sla_minutes: float | None, percentile: int | None) -> Tuple[pd.DataFrame, float]:
    d = df.copy()
    if sla_minutes is not None:
        tau = float(sla_minutes)
    elif percentile is not None:
        tau = float(np.nanpercentile(d["Delivery_Time"], percentile))
    else:
        tau = float(np.nanmedian(d["Delivery_Time"]))
    d["Delay_Flag"] = (d["Delivery_Time"] > tau).astype(int)

    # Age bins
    bins = [0, 25, 35, 45, np.inf]
    labels = ["<25","25-34","35-44","45+"]
    d["Age_Bin"] = pd.cut(d["Agent_Age"], bins=bins, labels=labels, include_lowest=True)

    return d, tau

def compute_kpis(d: pd.DataFrame) -> Tuple[float, float, int]:
    avg_time = float(d["Delivery_Time"].mean()) if len(d) else np.nan
    delay_rate = float(d["Delay_Flag"].mean()*100) if len(d) else np.nan
    n = int(len(d))
    return avg_time, delay_rate, n

def group_metrics(d: pd.DataFrame, by: str) -> pd.DataFrame:
    g = d.groupby(by, dropna=False).agg(
        avg_time=("Delivery_Time","mean"),
        delay_rate=("Delay_Flag","mean"),
        n=("Delivery_Time","size")
    ).reset_index()
    g["delay_rate"] = g["delay_rate"] * 100
    # Sort with more delayed first as default
    g = g.sort_values(["delay_rate","avg_time"], ascending=[False, False])
    return g

def warn_small_n(df: pd.DataFrame, threshold: int = 20) -> pd.DataFrame:
    df = df.copy()
    df["note"] = np.where(df["n"] < threshold, "Low volume", "")
    return df

# ---------- Load ----------
DATA_PATH = "data/Last mile Delivery Data.xlsx"  # Place the Excel file here
df_raw = load_data(DATA_PATH)

# ---------- Sidebar ----------
st.sidebar.header("Filters")
st.sidebar.caption("Adjust thresholds and selections to update all KPIs and charts.")

use_fixed_sla = st.sidebar.toggle("Use fixed SLA (minutes)", value=True)
if use_fixed_sla:
    sla = st.sidebar.number_input("SLA threshold (minutes)", min_value=1.0, value=40.0, step=1.0)
    df, tau = derive_features(df_raw, sla_minutes=sla, percentile=None)
else:
    pct = st.sidebar.slider("Delay percentile threshold", 50, 95, 75, 1)
    df, tau = derive_features(df_raw, sla_minutes=None, percentile=pct)

multis: Dict[str, List[str]] = {}
for c in ["Traffic","Weather","Vehicle","Area","Category"]:
    opts = sorted([x for x in df[c].dropna().unique().tolist()])
    default = opts
    multis[c] = st.sidebar.multiselect(c, opts, default=default)

# Sliders for numeric ranges
rating_min = float(np.nanmin(df["Agent_Rating"])) if df["Agent_Rating"].notna().any() else 0.0
rating_max = float(np.nanmax(df["Agent_Rating"])) if df["Agent_Rating"].notna().any() else 5.0
age_min = int(np.nanmin(df["Agent_Age"])) if df["Agent_Age"].notna().any() else 18
age_max = int(np.nanmax(df["Agent_Age"])) if df["Agent_Age"].notna().any() else 60
rating_sel = st.sidebar.slider("Agent_Rating range", rating_min, rating_max, (rating_min, rating_max))
age_sel = st.sidebar.slider("Agent_Age range", age_min, age_max, (age_min, age_max))

# ---------- Apply filters ----------
df_f = df.copy()
for c, vals in multis.items():
    if vals:
        df_f = df_f[df_f[c].isin(vals)]
df_f = df_f[df_f["Agent_Rating"].between(*rating_sel)]
df_f = df_f[df_f["Agent_Age"].between(*age_sel)]

# ---------- KPI Header ----------
st.title("Last-Mile Delivery Analytics Dashboard")
k1, k2, k3 = st.columns([1,1,2])
avg_time, delay_rate, n_obs = compute_kpis(df_f)
with k1:
    st.metric("Average Delivery Time (min)", f"{avg_time:.1f}" if pd.notna(avg_time) else "—")
with k2:
    st.metric("Delay Rate (%)", f"{delay_rate:.1f}" if pd.notna(delay_rate) else "—")
with k3:
    st.write(f"Records: {n_obs} | Delay threshold (τ): {tau:.1f} minutes")

st.divider()

# ---------- Delay Analyzer ----------
st.subheader("Delay Analyzer")
c1, c2 = st.columns(2)

def layered_bar(table: pd.DataFrame, xcol: str):
    table = warn_small_n(table)
    base = alt.Chart(table).encode(x=alt.X(f"{xcol}:N", sort='-y'))
    bars = base.mark_bar(color="#4F8EF7").encode(
        y=alt.Y("avg_time:Q", title="Avg Time (min)"),
        tooltip=[xcol, alt.Tooltip("avg_time:Q", format=".1f"), alt.Tooltip("delay_rate:Q", format=".1f", title="Delay Rate (%)"), "n","note"]
    )
    points = base.mark_point(size=90, filled=True, color="#E45756").encode(
        y=alt.Y("delay_rate:Q", axis=alt.Axis(title="Delay Rate (%)")),
        tooltip=[xcol, alt.Tooltip("delay_rate:Q", format=".1f"), "n","note"]
    )
    return alt.layer(bars, points).resolve_scale(y='independent').properties(height=320)

with c1:
    g_tr = group_metrics(df_f, "Traffic")
    st.altair_chart(layered_bar(g_tr, "Traffic"), use_container_width=True)
with c2:
    g_we = group_metrics(df_f, "Weather")
    st.altair_chart(layered_bar(g_we, "Weather"), use_container_width=True)

st.caption("Identify conditions driving delays to adjust buffers, routing, and contingency planning.")

st.divider()

# ---------- Vehicle Comparison ----------
st.subheader("Vehicle Comparison")
# Altair boxplot
box = alt.Chart(df_f).mark_boxplot(outliers={'color': '#E45756'}).encode(
    x=alt.X("Vehicle:N", title=None),
    y=alt.Y("Delivery_Time:Q", title="Delivery Time (min)"),
    color=alt.Color("Vehicle:N", legend=None),
    tooltip=[alt.Tooltip("Vehicle:N", title="Vehicle")]
).properties(height=330)
st.altair_chart(box, use_container_width=True)
st.caption("Assess speed and consistency to optimize fleet usage.")

st.divider()

# ---------- Agent Insights ----------
st.subheader("Agent Insights")
# Aggregate by rating (optionally bin rating if very granular)
# Here we show per-delivery scatter colored by Age_Bin
scatter = alt.Chart(df_f).mark_circle(size=64, opacity=0.7).encode(
    x=alt.X("Agent_Rating:Q", title="Agent Rating"),
    y=alt.Y("Delivery_Time:Q", title="Delivery Time (min)"),
    color=alt.Color("Age_Bin:N", title="Age Bin"),
    tooltip=[alt.Tooltip("Agent_Rating:Q", format=".1f"), "Agent_Age","Delivery_Time","Vehicle","Area","Category"]
).properties(height=340)
# Add trendline via transform_regression
trend = scatter.transform_regression("Agent_Rating","Delivery_Time").mark_line(color="#555", strokeDash=[6,3])
st.altair_chart(scatter + trend, use_container_width=True)
st.caption("Target training and assignments based on performance patterns.")

st.divider()

# ---------- Areas & Categories ----------
st.subheader("Areas & Categories")
g_area = group_metrics(df_f, "Area").sort_values("delay_rate", ascending=False)
bar_area = alt.Chart(g_area).mark_bar(color="#F2A541").encode(
    x=alt.X("Area:N", sort="-y"),
    y=alt.Y("delay_rate:Q", title="Delay Rate (%)"),
    tooltip=["Area", alt.Tooltip("delay_rate:Q", format=".1f"), "n"]
).properties(height=330)
st.altair_chart(bar_area, use_container_width=True)

# Heatmap Area x Category of delay rate
pivot = df_f.pivot_table(index="Area", columns="Category", values="Delay_Flag", aggfunc="mean")
heat_df = (pivot*100).reset_index().melt(id_vars="Area", var_name="Category", value_name="delay_rate").fillna(0)
heat = alt.Chart(heat_df).mark_rect().encode(
    x=alt.X("Category:N", title="Category"),
    y=alt.Y("Area:N", title="Area"),
    color=alt.Color("delay_rate:Q", title="Delay Rate (%)", scale=alt.Scale(scheme="redyellowblue")),
    tooltip=["Area","Category", alt.Tooltip("delay_rate:Q", format=".1f")]
).properties(height=380)
st.altair_chart(heat, use_container_width=True)
st.caption("Pinpoint hotspots where location and product type combine to create bottlenecks.")

st.divider()

# ---------- Export ----------
st.subheader("Export Filtered Summaries")
galls = {
    "by_traffic": g_tr,
    "by_weather": g_we,
    "by_vehicle": group_metrics(df_f, "Vehicle"),
    "by_area": g_area,
    "by_category": group_metrics(df_f, "Category")
}
all_df = pd.concat({k: v for k, v in galls.items()}, names=["group"]).reset_index()
csv_bytes = all_df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV snapshot", data=csv_bytes, file_name="filtered_summaries.csv", mime="text/csv")

# ---------- Footer ----------
st.write("---")
st.caption("Data logic: Load → Clean/Standardize → Derive Delay_Flag & Age_Bin → Aggregate → Apply Filters → Update KPIs & Visuals → Export.")
