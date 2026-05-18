from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
MART_DIR = ROOT / "data" / "chargenet" / "marts"
PORTFOLIO_DATA_DIR = ROOT / "docs" / "portfolio" / "data"
APP_DATA_DIR = ROOT / "app_data"
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


@st.cache_data
def load_optimization_results() -> pd.DataFrame:
    full_path = MART_DIR / "mart_optimization_results_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "optimization_results_tile_smoke.csv"
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    numeric_cols = [
        "selected_candidate_count",
        "objective_covered_demand_weight",
        "coverage_floor_demand_weight",
        "covered_zone_count",
        "total_candidate_cost",
        "budget",
        "k",
        "candidate_pool_count",
        "improvement_vs_baseline_demand_weight",
        "improvement_vs_baseline_pct",
        "cost_saving_vs_baseline",
        "cost_saving_vs_baseline_pct",
    ]
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    data["method_label"] = data["method_id"].map(method_label).fillna(data["method_id"])
    return data


@st.cache_data
def load_optimization_sensitivity() -> pd.DataFrame:
    full_path = MART_DIR / "mart_optimization_sensitivity_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "optimization_sensitivity_tile_smoke.csv"
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    numeric_cols = [
        "shortlist_size",
        "candidate_pool_count",
        "selected_candidate_count",
        "objective_covered_demand_weight",
        "base_weight_set_objective",
        "objective_delta_vs_base_weight_set",
        "objective_delta_vs_base_weight_set_pct",
        "overlap_with_base_solution_count",
        "overlap_with_base_solution_pct",
        "covered_zone_count",
        "total_candidate_cost",
        "budget",
        "k",
    ]
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_optimization_selected_sites() -> pd.DataFrame:
    full_path = MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "optimization_selected_sites_tile_smoke.csv"
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    for col in ["selection_rank", "baseline_rank_within_scenario", "baseline_score", "c_j"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


def method_label(method_id: str) -> str:
    labels = {
        "method:baseline-topk": "Baseline top-k",
        "method:mclp-shortlist-exact": "Exact shortlist MCLP",
        "method:mclp-pulp-cbc": "MILP max coverage",
        "method:min-cost-coverage-pulp": "MILP min cost floor",
        "method:mclp-weighted-shortlist-pulp-cbc": "MILP weight sensitivity",
    }
    return labels.get(method_id, method_id)


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


def plot_optimization_methods(data: pd.DataFrame, scenario_id: str) -> plt.Figure:
    plot_data = data[data["scenario_id"] == scenario_id].sort_values("objective_covered_demand_weight")
    fig, ax = plt.subplots(figsize=(10, 5.2))
    colors = ["#9a7b4f" if "min cost" in label.lower() else "#4f7292" for label in plot_data["method_label"]]
    ax.barh(plot_data["method_label"], plot_data["objective_covered_demand_weight"] / 1_000_000, color=colors)
    ax.set_xlabel("Covered demand proxy (millions)")
    ax.set_title("Phase 5 Method Comparison", fontsize=14, weight="bold")
    ax.grid(axis="x", color="#e2ded6")
    ax.spines[["top", "right", "left"]].set_visible(False)
    return fig


def plot_optimization_sensitivity(data: pd.DataFrame, scenario_id: str) -> plt.Figure:
    plot_data = data[data["scenario_id"] == scenario_id].sort_values("objective_delta_vs_base_weight_set")
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.barh(plot_data["weight_set_name"], plot_data["objective_delta_vs_base_weight_set"] / 1_000_000, color="#6c8ead")
    ax.axvline(0, color="#25324d", linewidth=1)
    ax.set_xlabel("Objective delta vs base weight set (millions)")
    ax.set_title("MILP Sensitivity By Weight Set", fontsize=14, weight="bold")
    ax.grid(axis="x", color="#e2ded6")
    ax.spines[["top", "right", "left"]].set_visible(False)
    return fig


metrics = load_metrics()

with st.sidebar:
    st.title("ChargeNet Europe")
    st.warning(DISCLAIMER)
    st.caption("Scope: Belgium, Germany, France, Netherlands.")
    st.caption("Status: Phase 4 complete. Phase 5 MILP MVP uses public proxies and unit-cost assumptions.")
    if metrics:
        st.metric("Demand zones", f"{int(metrics.get('demand_zones', 0)):,}")
        st.metric("Candidate proxies", f"{int(metrics.get('candidate_sites', 0)):,}")
        st.metric("QA failures", f"{int(metrics.get('raw_failures', 0)) + int(metrics.get('clean_failures', 0))}")

st.title("ChargeNet Europe")
st.caption("Public-data EV charging expansion diligence for four pilot countries.")

tab_top, tab_sensitivity, tab_optimization, tab_method, tab_coverage = st.tabs(
    ["Top Candidates", "Sensitivity Analysis", "Optimization", "Methodology", "Coverage Map"]
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

with tab_optimization:
    st.subheader("Phase 5 Optimization")
    optimization = load_optimization_results()
    optimization_sensitivity = load_optimization_sensitivity()
    selected_sites = load_optimization_selected_sites()
    scenario_ids = sorted(optimization["scenario_id"].dropna().unique().tolist())
    default_index = scenario_ids.index(BASE_SCENARIO) if BASE_SCENARIO in scenario_ids else 0
    selected_scenario = st.selectbox("Scenario", scenario_ids, index=default_index)
    scenario_results = optimization[optimization["scenario_id"] == selected_scenario].copy()
    baseline = scenario_results[scenario_results["method_id"] == "method:baseline-topk"]
    max_coverage = scenario_results[scenario_results["method_id"] == "method:mclp-pulp-cbc"]
    min_cost = scenario_results[scenario_results["method_id"] == "method:min-cost-coverage-pulp"]
    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Best covered demand proxy", f"{scenario_results['objective_covered_demand_weight'].max() / 1_000_000:.1f}M")
    with metric_cols[1]:
        uplift = float(max_coverage["improvement_vs_baseline_pct"].iloc[0]) if not max_coverage.empty else 0.0
        st.metric("MILP uplift vs baseline", f"{uplift:.1%}")
    with metric_cols[2]:
        saving = float(min_cost["cost_saving_vs_baseline_pct"].iloc[0]) if not min_cost.empty else 0.0
        st.metric("Min-cost saving vs baseline", f"{saving:.1%}")
    st.pyplot(plot_optimization_methods(optimization, selected_scenario), width="stretch")
    display_cols = [
        "method_label",
        "objective_type",
        "solver_status",
        "selected_candidate_count",
        "objective_covered_demand_weight",
        "coverage_floor_demand_weight",
        "covered_zone_count",
        "total_candidate_cost",
        "improvement_vs_baseline_pct",
        "cost_saving_vs_baseline_pct",
    ]
    st.dataframe(
        scenario_results[display_cols],
        width="stretch",
        hide_index=True,
        column_config={
            "method_label": "Method",
            "objective_covered_demand_weight": st.column_config.NumberColumn("Covered demand proxy", format="%.0f"),
            "coverage_floor_demand_weight": st.column_config.NumberColumn("Coverage floor", format="%.0f"),
            "total_candidate_cost": st.column_config.NumberColumn("Cost proxy", format="%.0f"),
            "improvement_vs_baseline_pct": st.column_config.NumberColumn("Coverage uplift", format="%.1%"),
            "cost_saving_vs_baseline_pct": st.column_config.NumberColumn("Cost saving", format="%.1%"),
        },
    )
    st.download_button(
        "Download scenario optimization CSV",
        scenario_results.to_csv(index=False).encode("utf-8"),
        file_name=f"{selected_scenario.replace(':', '_')}_optimization.csv",
        mime="text/csv",
    )

    st.subheader("Optimization Sensitivity")
    st.pyplot(plot_optimization_sensitivity(optimization_sensitivity, selected_scenario), width="stretch")
    sensitivity_cols = [
        "weight_set_name",
        "solver_status",
        "shortlist_size",
        "selected_candidate_count",
        "objective_covered_demand_weight",
        "objective_delta_vs_base_weight_set_pct",
        "overlap_with_base_solution_pct",
        "total_candidate_cost",
    ]
    st.dataframe(
        optimization_sensitivity[optimization_sensitivity["scenario_id"] == selected_scenario][sensitivity_cols],
        width="stretch",
        hide_index=True,
        column_config={
            "weight_set_name": "Weight set",
            "objective_covered_demand_weight": st.column_config.NumberColumn("Covered demand proxy", format="%.0f"),
            "objective_delta_vs_base_weight_set_pct": st.column_config.NumberColumn("Delta vs base", format="%.1%"),
            "overlap_with_base_solution_pct": st.column_config.NumberColumn("Solution overlap", format="%.1%"),
            "total_candidate_cost": st.column_config.NumberColumn("Cost proxy", format="%.0f"),
        },
    )
    selected_method = st.selectbox("Selected-site detail", scenario_results["method_label"].tolist())
    method_id = scenario_results.loc[scenario_results["method_label"] == selected_method, "method_id"].iloc[0]
    site_rows = selected_sites[(selected_sites["scenario_id"] == selected_scenario) & (selected_sites["method_id"] == method_id)]
    st.dataframe(
        site_rows[["selection_rank", "candidate_site_id", "country_code", "nuts_id", "site_type", "baseline_rank_within_scenario", "c_j"]],
        width="stretch",
        hide_index=True,
        column_config={
            "selection_rank": "Selection rank",
            "candidate_site_id": "Candidate ID",
            "baseline_rank_within_scenario": "Baseline rank",
            "c_j": st.column_config.NumberColumn("Cost proxy", format="%.0f"),
        },
    )
    st.caption(
        "Phase 5 uses public POI proxies, straight-line coverage, population demand weights, and unit-cost assumptions. "
        "It is an optimization checkpoint for diligence, not an investment-grade site decision."
    )

with tab_method:
    st.subheader("Methodology")
    st.markdown(
        """
        The current demo presents the Phase 4 baseline and Phase 5 MILP checkpoint. Candidate sites are
        OpenStreetMap POI proxies, demand zones are NUTS3 regions, and population is used as a
        demand proxy. The baseline score combines coverage, data quality, rollout risk, and
        competition. Five weight sets test whether rankings and optimization shortlists depend on
        one fragile assumption set.

        Full methodology: [GitHub README](https://github.com/tasohub/chargenet-europe#readme)
        and `docs/portfolio/METHODOLOGY.md`.

        Phase 5 is a public-proxy MILP checkpoint with max-coverage and min-cost formulations.
        It does not model grid capacity, permits, land availability, traffic flows, or negotiated CAPEX.
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
