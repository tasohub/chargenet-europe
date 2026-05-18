from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
MART_DIR = ROOT / "data" / "chargenet" / "marts"
PORTFOLIO_DATA_DIR = ROOT / "docs" / "portfolio" / "data"
BASE_SCENARIO = "scenario:radius-base"

DISCLAIMER = (
    "Decision-support layer for early-stage diligence only. "
    "Not investment advice. All data is public. Outputs are illustrative."
)


st.set_page_config(page_title="ChargeNet Europe", page_icon="EV", layout="wide")

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 2rem; max-width: 1200px;}
    h1, h2, h3 {color: #25324d;}
    .metric-card {
        background: #f8f7f2;
        border: 1px solid #ddd6c9;
        padding: 16px;
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_metrics() -> dict:
    path = PORTFOLIO_DATA_DIR / "metrics.json"
    if path.exists():
        return pd.read_json(path, typ="series").to_dict()
    return {}


@st.cache_data
def load_top_candidates() -> pd.DataFrame:
    full_path = MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv"
    if full_path.exists():
        data = pd.read_csv(full_path)
        data = data[data["scenario_id"] == BASE_SCENARIO].copy()
        numeric_cols = [
            "rank_within_scenario",
            "baseline_score",
            "coverage_component",
            "data_quality_component",
            "risk_component",
            "competition_component",
            "covered_zone_count",
            "covered_demand_weight",
            "avg_distance_covered_km",
        ]
        for col in numeric_cols:
            data[col] = pd.to_numeric(data[col], errors="coerce")
        data = data.sort_values("rank_within_scenario").head(50)
        data["candidate_short_id"] = data["candidate_site_id"].str.replace("candidate:osm:", "", regex=False)
        return data
    return pd.read_csv(PORTFOLIO_DATA_DIR / "top_candidates.csv")


@st.cache_data
def load_sensitivity() -> pd.DataFrame:
    full_path = MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv"
    if full_path.exists():
        data = pd.read_csv(full_path)
        data = data[data["scenario_id"] == BASE_SCENARIO].copy()
        for col in ["rank_within_weight_set_scenario", "base_rank_within_scenario", "rank_delta_vs_base", "weighted_score"]:
            data[col] = pd.to_numeric(data[col], errors="coerce")
        data["candidate_short_id"] = data["candidate_site_id"].str.replace("candidate:osm:", "", regex=False)
        return data
    return pd.read_csv(PORTFOLIO_DATA_DIR / "sensitivity_rank_shift.csv")


@st.cache_data
def load_country_summary() -> pd.DataFrame:
    return pd.read_csv(PORTFOLIO_DATA_DIR / "country_coverage_summary.csv")


def plot_rank_shift(data: pd.DataFrame, weight_a: str, weight_b: str) -> plt.Figure:
    subset = data[data["weight_set_name"].isin([weight_a, weight_b])].copy()
    movers = (
        subset.groupby("candidate_short_id")["rank_delta_vs_base"]
        .apply(lambda s: s.abs().max())
        .sort_values(ascending=False)
        .head(15)
        .index
    )
    subset = subset[subset["candidate_short_id"].isin(movers)]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for label, group in subset.groupby("weight_set_name"):
        group = group.sort_values("rank_delta_vs_base")
        ax.barh(group["candidate_short_id"] + "  " + label[:11], group["rank_delta_vs_base"], label=label)
    ax.axvline(0, color="#25324d", linewidth=1)
    ax.set_title("Rank Delta vs Base", fontsize=14, weight="bold")
    ax.set_xlabel("Rank delta; negative means rank improved")
    ax.grid(axis="x", color="#e2ded6")
    ax.spines[["top", "right", "left"]].set_visible(False)
    return fig


def plot_country_summary(data: pd.DataFrame) -> plt.Figure:
    plot_data = data.sort_values("candidate_coverage_rate")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(plot_data["country_code"], plot_data["candidate_coverage_rate"] * 100, color="#6c8ead")
    for i, row in enumerate(plot_data.itertuples()):
        ax.text(row.candidate_coverage_rate * 100 + 1, i, f"{row.candidates_with_coverage}/{row.candidate_count}", va="center")
    ax.set_xlim(0, 105)
    ax.set_xlabel("Candidates with at least one covered NUTS3 zone (%)")
    ax.set_title("Coverage Signal By Pilot Country", fontsize=14, weight="bold")
    ax.grid(axis="x", color="#e2ded6")
    ax.spines[["top", "right", "left"]].set_visible(False)
    return fig


metrics = load_metrics()

with st.sidebar:
    st.title("ChargeNet Europe")
    st.warning(DISCLAIMER)
    st.caption("Scope: Belgium, Germany, France, Netherlands.")
    st.caption("Status: Phase 4 complete. Phase 5 MILP in progress.")
    if metrics:
        st.metric("Demand zones", f"{int(metrics.get('demand_zones', 0)):,}")
        st.metric("Candidate proxies", f"{int(metrics.get('candidate_sites', 0)):,}")
        st.metric("QA failures", f"{int(metrics.get('raw_failures', 0)) + int(metrics.get('clean_failures', 0))}")

st.title("ChargeNet Europe")
st.caption("Public-data EV charging expansion diligence for four pilot countries.")

tab_top, tab_sensitivity, tab_method, tab_coverage = st.tabs(
    ["Top Candidates", "Sensitivity Analysis", "Methodology", "Coverage Map"]
)

with tab_top:
    st.subheader("Top 50 Baseline Candidates")
    top = load_top_candidates()
    display_cols = [
        "rank_within_scenario",
        "candidate_short_id",
        "country_code",
        "nuts_id",
        "site_type",
        "baseline_score",
        "coverage_component",
        "data_quality_component",
        "risk_component",
        "competition_component",
        "covered_zone_count",
        "covered_demand_weight",
    ]
    st.dataframe(
        top[display_cols],
        width="stretch",
        hide_index=True,
        column_config={
            "rank_within_scenario": "Rank",
            "candidate_short_id": "Candidate",
            "baseline_score": st.column_config.NumberColumn("Score", format="%.3f"),
            "covered_demand_weight": st.column_config.NumberColumn("Covered demand proxy", format="%.0f"),
        },
    )

with tab_sensitivity:
    st.subheader("Sensitivity Analysis")
    sensitivity = load_sensitivity()
    weight_names = sorted(sensitivity["weight_set_name"].dropna().unique().tolist())
    default_a = "Base balanced" if "Base balanced" in weight_names else weight_names[0]
    default_b = "Data quality guardrail" if "Data quality guardrail" in weight_names else weight_names[-1]
    col_a, col_b = st.columns(2)
    with col_a:
        weight_a = st.selectbox("Weight set A", weight_names, index=weight_names.index(default_a))
    with col_b:
        weight_b = st.selectbox("Weight set B", weight_names, index=weight_names.index(default_b))
    st.pyplot(plot_rank_shift(sensitivity, weight_a, weight_b), width="stretch")
    st.caption("Rank shifts are shown against the base ranking. Negative values mean a candidate moved up.")

with tab_method:
    st.subheader("Methodology")
    st.markdown(
        """
        The current demo presents the Phase 4 baseline and sensitivity layer. Candidate sites are
        OpenStreetMap POI proxies, demand zones are NUTS3 regions, and population is used as a
        demand proxy. The baseline score combines coverage, data quality, rollout risk, and
        competition. Five weight sets test whether rankings depend on one fragile assumption set.

        Full methodology: [GitHub README](https://github.com/tasohub/chargenet-europe#readme)
        and `docs/portfolio/METHODOLOGY.md`.

        Phase 5 MILP facility-location optimization is in progress and is not presented here as a
        final site-selection recommendation.
        """
    )

with tab_coverage:
    st.subheader("Coverage Signal")
    country = load_country_summary()
    st.pyplot(plot_country_summary(country), width="stretch")
    st.caption(
        "A lightweight bar chart is used instead of a choropleth because the public portfolio package "
        "does not ship full GIS polygons or large coverage matrices."
    )
