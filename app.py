from __future__ import annotations

from html import escape
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from chargenet.app_summary import (
    build_candidate_drilldown,
    build_country_concentration_guardrails,
    build_decision_flags,
    build_metric_glossary,
    build_optimization_takeaways,
    build_recruiter_kpis,
    build_scenario_cards,
    build_top_candidate_insights,
    build_weight_set_comparison,
)
from chargenet.scenarios import cost_proxy_explanation_rows


ROOT = Path(__file__).resolve().parent
MART_DIR = ROOT / "data" / "chargenet" / "marts"
REPORT_DIR = ROOT / "reports" / "chargenet"
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
    .hero-panel {
        background: #f7f5ee;
        border: 1px solid #d9d2c3;
        border-left: 6px solid #587d71;
        padding: 18px 20px;
        border-radius: 6px;
        margin: 10px 0 16px 0;
    }
    .hero-kicker {
        color: #587d71;
        font-size: 0.82rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 6px;
    }
    .hero-title {
        color: #25324d;
        font-size: 1.55rem;
        font-weight: 700;
        line-height: 1.25;
        margin: 0 0 8px 0;
    }
    .hero-copy {
        color: #4a4f5c;
        font-size: 0.98rem;
        line-height: 1.5;
        margin: 0;
    }
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 10px;
        margin: 12px 0 18px 0;
    }
    .kpi-card {
        background: #ffffff;
        border: 1px solid #dfe3df;
        border-top: 4px solid #6c8ead;
        padding: 12px 12px 13px 12px;
        border-radius: 6px;
        min-height: 118px;
    }
    .kpi-card.pass { border-top-color: #587d71; }
    .kpi-card.fail { border-top-color: #a85f4e; }
    .kpi-label {
        color: #606775;
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .kpi-value {
        color: #25324d;
        font-size: 1.45rem;
        font-weight: 760;
        margin-top: 6px;
    }
    .kpi-caption {
        color: #5d6370;
        font-size: 0.78rem;
        line-height: 1.35;
        margin-top: 6px;
    }
    .story-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
        margin: 4px 0 20px 0;
    }
    .story-step {
        background: #f9faf8;
        border: 1px solid #dfe3df;
        padding: 12px;
        border-radius: 6px;
        min-height: 108px;
    }
    .story-step strong {
        color: #25324d;
        display: block;
        margin-bottom: 6px;
    }
    .story-step span {
        color: #555d68;
        font-size: 0.85rem;
        line-height: 1.38;
    }
    .insight-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
        margin: 8px 0 14px 0;
    }
    .insight-card {
        background: #ffffff;
        border: 1px solid #e1e4df;
        border-left: 4px solid #9a7b4f;
        padding: 11px 12px;
        border-radius: 6px;
        min-height: 96px;
    }
    .insight-label {
        color: #626977;
        font-size: 0.74rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .insight-value {
        color: #25324d;
        font-size: 1.25rem;
        font-weight: 760;
        margin-top: 5px;
    }
    .insight-caption {
        color: #5d6370;
        font-size: 0.78rem;
        line-height: 1.34;
        margin-top: 5px;
    }
    .scenario-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin: 8px 0 16px 0;
    }
    .scenario-card {
        background: #fbfbf8;
        border: 1px solid #dfe3df;
        border-left: 4px solid #4f7292;
        padding: 12px;
        border-radius: 6px;
        min-height: 172px;
    }
    .scenario-card strong {
        color: #25324d;
        display: block;
        font-size: 0.95rem;
        line-height: 1.25;
        margin-bottom: 7px;
    }
    .scenario-question {
        color: #515966;
        font-size: 0.82rem;
        line-height: 1.35;
        min-height: 44px;
        margin-bottom: 8px;
    }
    .scenario-meta {
        color: #5d6370;
        font-size: 0.76rem;
        line-height: 1.35;
        margin-top: 5px;
    }
    .drilldown-panel {
        background: #f9faf8;
        border: 1px solid #dfe3df;
        border-left: 4px solid #587d71;
        padding: 12px;
        border-radius: 6px;
        margin: 8px 0 12px 0;
    }
    .drilldown-panel strong {
        color: #25324d;
        display: block;
        margin-bottom: 5px;
    }
    .drilldown-panel span {
        color: #555d68;
        font-size: 0.85rem;
        line-height: 1.4;
    }
    @media (max-width: 900px) {
        .kpi-grid, .story-strip, .insight-grid, .scenario-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 560px) {
        .kpi-grid, .story-strip, .insight-grid, .scenario-grid { grid-template-columns: 1fr; }
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
    if not full_path.exists() and not fallback_path.exists():
        return pd.DataFrame()
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
def load_optimization_diagnostics() -> pd.DataFrame:
    full_path = MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "optimization_constraint_diagnostics_tile_smoke.csv"
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    for col in ["lhs_value", "rhs_value", "slack_value"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    data["method_label"] = data["method_id"].map(method_label).fillna(data["method_id"])
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


@st.cache_data
def load_optimization_zone_trace() -> pd.DataFrame:
    full_path = MART_DIR / "fact_optimization_zone_trace_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "optimization_zone_trace_tile_smoke.csv"
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    for col in ["selection_rank", "zone_coverage_rank", "coverage_radius_km", "distance_km", "zone_demand_weight", "zone_demand_share_of_candidate"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_optimization_country_diagnostics() -> pd.DataFrame:
    full_path = MART_DIR / "mart_optimization_country_diagnostics_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "optimization_country_diagnostics_tile_smoke.csv"
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    for col in [
        "selected_candidate_count",
        "covered_zone_count",
        "covered_demand_weight",
        "covered_demand_share_of_method",
        "total_candidate_cost",
        "candidate_cost_share_of_method",
        "concentration_warning_threshold",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_method_comparison_narrative() -> pd.DataFrame:
    full_path = MART_DIR / "mart_method_comparison_narrative_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "method_comparison_narrative_tile_smoke.csv"
    if not full_path.exists() and not fallback_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    for col in [
        "baseline_covered_demand_weight",
        "mclp_covered_demand_weight",
        "min_cost_covered_demand_weight",
        "mclp_coverage_uplift_pct",
        "min_cost_saving_pct",
        "dominant_coverage_country_share",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_candidate_lineage_trace() -> pd.DataFrame:
    full_path = MART_DIR / "mart_candidate_lineage_trace_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "candidate_lineage_trace_tile_smoke.csv"
    if not full_path.exists() and not fallback_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    for col in [
        "selection_rank",
        "baseline_rank_within_scenario",
        "baseline_score",
        "covered_zone_count",
        "covered_demand_weight",
        "scenario_candidate_cost",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_business_scenarios() -> pd.DataFrame:
    full_path = MART_DIR / "mart_business_scenario_library_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "business_scenario_library_tile_smoke.csv"
    if not full_path.exists() and not fallback_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    for col in [
        "selected_candidate_count",
        "primary_metric_value",
        "covered_demand_weight",
        "total_candidate_cost",
        "comparison_value",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_pipeline_snapshot_metrics() -> pd.DataFrame:
    full_path = MART_DIR / "mart_pipeline_snapshot_metrics_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "pipeline_snapshot_metrics_tile_smoke.csv"
    if not full_path.exists() and not fallback_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    data["metric_value"] = pd.to_numeric(data["metric_value"], errors="coerce")
    return data


@st.cache_data
def load_pipeline_snapshot_drift() -> pd.DataFrame:
    full_path = MART_DIR / "mart_pipeline_snapshot_drift_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "pipeline_snapshot_drift_tile_smoke.csv"
    if not full_path.exists() and not fallback_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    for col in [
        "current_metric_value",
        "reference_metric_value",
        "absolute_delta",
        "relative_delta_pct",
        "warning_threshold_pct",
        "fail_threshold_pct",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_pipeline_snapshot_certifications() -> pd.DataFrame:
    full_path = MART_DIR / "mart_pipeline_snapshot_certifications_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "pipeline_snapshot_certifications_tile_smoke.csv"
    if not full_path.exists() and not fallback_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    if "metric_count" in data.columns:
        data["metric_count"] = pd.to_numeric(data["metric_count"], errors="coerce")
    return data


@st.cache_data
def load_release_gate() -> pd.DataFrame:
    full_path = REPORT_DIR / "release_gate_tile_smoke.csv"
    fallback_path = APP_DATA_DIR / "release_gate_tile_smoke.csv"
    if not full_path.exists() and not fallback_path.exists():
        return pd.DataFrame()
    data = pd.read_csv(full_path if full_path.exists() else fallback_path)
    if "blocker_count" in data.columns:
        data["blocker_count"] = pd.to_numeric(data["blocker_count"], errors="coerce")
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


def render_recruiter_kpis(kpis: list[dict]) -> None:
    cards = []
    for kpi in kpis:
        cards.append(
            "\n".join(
                [
                    f"<div class='kpi-card {escape(str(kpi.get('status', 'neutral')))}'>",
                    f"<div class='kpi-label'>{escape(str(kpi['label']))}</div>",
                    f"<div class='kpi-value'>{escape(str(kpi['value']))}</div>",
                    f"<div class='kpi-caption'>{escape(str(kpi['caption']))}</div>",
                    "</div>",
                ]
            )
        )
    st.markdown(f"<div class='kpi-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_story_strip() -> None:
    steps = [
        (
            "Problem",
            "Where should an EV operator prioritize charger expansion across four pilot countries?",
        ),
        (
            "Method",
            "Score candidates, stress-test assumptions, then solve coverage and cost tradeoff scenarios.",
        ),
        (
            "Output",
            "A shortlist, scenario comparison, selected-site trace, and Power BI/Streamlit-ready marts.",
        ),
        (
            "Guardrail",
            "Public-facing text is scanned for overclaim risk; release gates check quality, drift, and demo render.",
        ),
    ]
    html = []
    for title, copy in steps:
        html.append(
            "\n".join(
                [
                    "<div class='story-step'>",
                    f"<strong>{escape(title)}</strong>",
                    f"<span>{escape(copy)}</span>",
                    "</div>",
                ]
            )
        )
    st.markdown(f"<div class='story-strip'>{''.join(html)}</div>", unsafe_allow_html=True)


def render_insight_cards(insights: list[dict]) -> None:
    cards = []
    for insight in insights:
        cards.append(
            "\n".join(
                [
                    "<div class='insight-card'>",
                    f"<div class='insight-label'>{escape(str(insight['label']))}</div>",
                    f"<div class='insight-value'>{escape(str(insight['value']))}</div>",
                    f"<div class='insight-caption'>{escape(str(insight['caption']))}</div>",
                    "</div>",
                ]
            )
        )
    st.markdown(f"<div class='insight-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_scenario_cards(cards_data: list[dict]) -> None:
    cards = []
    for card in cards_data:
        cards.append(
            "\n".join(
                [
                    "<div class='scenario-card'>",
                    f"<strong>{escape(str(card['business_scenario_name']))}</strong>",
                    f"<div class='scenario-question'>{escape(str(card['business_question']))}</div>",
                    f"<div class='scenario-meta'>Best method: {escape(str(card['best_method']))}</div>",
                    f"<div class='scenario-meta'>Covered demand: {escape(str(card['covered_demand']))}</div>",
                    f"<div class='scenario-meta'>Selected candidates: {escape(str(card['selected_candidates']))}</div>",
                    f"<div class='scenario-meta'>Stability: {escape(str(card['stability_signal']))}</div>",
                    f"<div class='scenario-meta'>Readout: {escape(str(card['decision_readout']))}</div>",
                    f"<div class='scenario-meta'>Next: {escape(str(card['recommended_next_action']))}</div>",
                    "</div>",
                ]
            )
        )
    st.markdown(f"<div class='scenario-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_candidate_drilldown(drilldown: dict) -> None:
    st.markdown(
        "\n".join(
            [
                "<div class='drilldown-panel'>",
                f"<strong>{escape(str(drilldown['candidate_site_id']))}</strong>",
                f"<span>Source: {escape(str(drilldown['source_record_id']))} | Tile: {escape(str(drilldown['tile_job_id']))}</span><br>",
                f"<span>Location: {escape(str(drilldown['country_code']))} / {escape(str(drilldown['nuts_id']))} | Type: {escape(str(drilldown['site_type']))}</span>",
                "</div>",
            ]
        ),
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    cols[0].metric("Selection rank", drilldown["selection_rank"])
    cols[1].metric("Baseline rank", drilldown["baseline_rank"])
    cols[2].metric("Score", drilldown["baseline_score"])
    cols[3].metric("Cost proxy", drilldown["scenario_candidate_cost"])
    cols[4].metric("Covered zones", drilldown["covered_zone_count"])
    with st.expander("Lineage details", expanded=False):
        st.write(f"Covered demand proxy: {drilldown['covered_demand_weight']}")
        st.write(f"Top covered zones: {drilldown['top_covered_zones']}")
        st.write(f"Raw OSM tag keys: {drilldown['raw_tag_keys']}")


metrics = load_metrics()
pipeline_snapshot = load_pipeline_snapshot_metrics()
pipeline_drift = load_pipeline_snapshot_drift()
pipeline_certifications = load_pipeline_snapshot_certifications()
release_gate = load_release_gate()
summary_optimization = load_optimization_results()
recruiter_kpis = build_recruiter_kpis(
    snapshot_rows=pipeline_snapshot.to_dict("records"),
    optimization_rows=summary_optimization.to_dict("records"),
    release_gate_rows=release_gate.to_dict("records"),
    demand_zone_count=int(metrics.get("demand_zones", 0)),
)

with st.sidebar:
    st.title("ChargeNet Europe")
    st.markdown("**Read this first**")
    st.info(
        "What this is: public-data EV charging expansion diligence.\n\n"
        "Headline: optimization covered 120 zones vs 8 for the simple top-10 in the aggressive-radius scenario.\n\n"
        f"Disclaimer: {DISCLAIMER}"
    )
    st.caption("Scope: Belgium, Germany, France, Netherlands.")
    st.caption("Status: Phase 5 optimization MVP complete. The model still uses public proxies and unit-cost assumptions.")
    release_kpi = next((kpi for kpi in recruiter_kpis if kpi["key"] == "release_gate"), None)
    if release_kpi:
        st.metric("Release gate", release_kpi["value"], release_kpi["caption"])
    if metrics:
        st.metric("Regions analyzed", f"{int(metrics.get('demand_zones', 0)):,}")
        st.metric("Locations screened", f"{int(metrics.get('candidate_sites', 0)):,}")
        st.metric("QA failures", f"{int(metrics.get('raw_failures', 0)) + int(metrics.get('clean_failures', 0))}")

st.title("ChargeNet Europe")
st.caption("Public-data EV charging expansion diligence for Belgium, Germany, France, and the Netherlands.")
st.markdown(
    """
    <div class='hero-panel'>
      <div class='hero-kicker'>Operations analytics portfolio demo</div>
      <div class='hero-title'>A decision-support workflow for EV charging expansion diligence.</div>
      <p class='hero-copy'>
        The demo turns public map, regional boundary, and population data into location screening,
        sensitivity analysis, and optimization outputs. It is built for early-stage business analysis:
        useful for prioritization, honest about public-proxy limits, and guarded by release checks before demo use.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
render_recruiter_kpis(recruiter_kpis)
render_story_strip()

tab_optimization, tab_top, tab_sensitivity, tab_coverage, tab_method = st.tabs(
    ["Optimization", "Top Candidates", "Sensitivity Analysis", "Coverage Map", "Methodology"]
)

with tab_top:
    st.subheader("Top 50 Baseline Candidates")
    top = load_top_candidates()
    st.caption(
        "Baseline ranking is a diligence shortlist, not a rollout instruction. "
        "Use it to see which public POI proxies look strongest before optimization."
    )
    render_insight_cards(build_top_candidate_insights(top.to_dict("records")))
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
    st.download_button(
        "Download top candidates CSV",
        top[display_cols].to_csv(index=False).encode("utf-8"),
        file_name="chargenet_top_candidates_radius_base.csv",
        mime="text/csv",
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
    comparison_rows = build_weight_set_comparison(sensitivity.to_dict("records"), weight_a, weight_b)
    comparison_df = pd.DataFrame(comparison_rows)
    if not comparison_df.empty:
        st.subheader("Side-by-side Rank Comparison")
        st.dataframe(
            comparison_df[
                [
                    "candidate_site_id",
                    "country_code",
                    "nuts_id",
                    "site_type",
                    "rank_a",
                    "rank_b",
                    "rank_shift_b_vs_a",
                    "weighted_score_a",
                    "weighted_score_b",
                ]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "candidate_site_id": "Candidate ID",
                "rank_a": f"Rank: {weight_a}",
                "rank_b": f"Rank: {weight_b}",
                "rank_shift_b_vs_a": "Rank shift B vs A",
                "weighted_score_a": st.column_config.NumberColumn(f"Score: {weight_a}", format="%.3f"),
                "weighted_score_b": st.column_config.NumberColumn(f"Score: {weight_b}", format="%.3f"),
            },
        )
        st.download_button(
            "Download weight-set comparison CSV",
            comparison_df.to_csv(index=False).encode("utf-8"),
            file_name="chargenet_weight_set_comparison.csv",
            mime="text/csv",
        )

with tab_optimization:
    st.subheader("Decision Summary")
    st.caption(
        "This view compares a simple baseline shortlist with optimization scenarios. "
        "The numbers are public-proxy diligence signals, not build recommendations."
    )
    optimization = load_optimization_results()
    optimization_sensitivity = load_optimization_sensitivity()
    optimization_diagnostics = load_optimization_diagnostics()
    selected_sites = load_optimization_selected_sites()
    zone_trace = load_optimization_zone_trace()
    country_diagnostics = load_optimization_country_diagnostics()
    method_comparison = load_method_comparison_narrative()
    lineage_trace = load_candidate_lineage_trace()
    business_scenarios = load_business_scenarios()
    scenario_ids = sorted(optimization["scenario_id"].dropna().unique().tolist()) if "scenario_id" in optimization.columns else []
    if not scenario_ids:
        st.warning("Optimization outputs are not available in the current app data bundle.")
        st.stop()
    default_index = scenario_ids.index(BASE_SCENARIO) if BASE_SCENARIO in scenario_ids else 0
    scenario_cards = build_scenario_cards(optimization.to_dict("records"), business_scenarios.to_dict("records"))
    if scenario_cards:
        st.subheader("Scenario Cards")
        render_scenario_cards(scenario_cards)
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
        st.metric("90% floor cost saving", f"{saving:.1%}")
    render_insight_cards(build_optimization_takeaways(optimization.to_dict("records"), selected_scenario))
    st.caption(
        "Cost-floor savings are measured against a 90% baseline-coverage floor; they are not like-for-like full-service savings."
    )
    st.pyplot(plot_optimization_methods(optimization, selected_scenario), width="stretch")
    method_narrative = method_comparison[method_comparison["scenario_id"] == selected_scenario].copy()
    if not method_narrative.empty:
        st.subheader("Method Comparison Narrative")
        narrative_cols = [
            "comparison_readout",
            "mclp_coverage_uplift_pct",
            "min_cost_saving_pct",
            "dominant_coverage_country_code",
            "dominant_coverage_country_share",
            "analyst_takeaway",
        ]
        st.dataframe(
            method_narrative[narrative_cols],
            width="stretch",
            hide_index=True,
            column_config={
                "comparison_readout": "Readout",
                "mclp_coverage_uplift_pct": st.column_config.NumberColumn("MCLP uplift", format="%.1%"),
                "min_cost_saving_pct": st.column_config.NumberColumn("Min-cost saving", format="%.1%"),
                "dominant_coverage_country_code": "Dominant country",
                "dominant_coverage_country_share": st.column_config.NumberColumn("Dominant share", format="%.1%"),
                "analyst_takeaway": "Analyst takeaway",
            },
        )
        decision_flags = pd.DataFrame(build_decision_flags(method_narrative.to_dict("records")))
        st.subheader("Decision Flags")
        st.dataframe(
            decision_flags,
            width="stretch",
            hide_index=True,
            column_config={
                "scenario_id": "Scenario",
                "primary_flag": "Primary flag",
                "coverage_uplift": "Coverage uplift",
                "min_cost_saving": "Min-cost saving",
                "dominant_country_share": "Dominant country share",
                "review_prompt": "Review prompt",
                "allowed_use_note": "Allowed use",
            },
        )
    if not business_scenarios.empty:
        st.subheader("Business Scenario Library")
        scenario_library_cols = [
            "business_scenario_name",
            "business_question",
            "primary_metric",
            "primary_metric_value",
            "comparison_label",
            "comparison_value",
            "solution_stability_signal",
            "decision_readout",
            "recommended_next_action",
        ]
        st.dataframe(
            business_scenarios[scenario_library_cols],
            width="stretch",
            hide_index=True,
            column_config={
                "business_scenario_name": "Scenario",
                "business_question": "Business question",
                "primary_metric": "Primary metric",
                "primary_metric_value": st.column_config.NumberColumn("Primary value", format="%.3f"),
                "comparison_label": "Comparison",
                "comparison_value": st.column_config.NumberColumn("Comparison value", format="%.3f"),
                "solution_stability_signal": "Stability signal",
                "decision_readout": "Readout",
                "recommended_next_action": "Next action",
            },
        )
    display_cols = [
        "method_label",
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
            "solver_status": "Status",
            "objective_covered_demand_weight": st.column_config.NumberColumn("Covered demand proxy", format="%.0f"),
            "coverage_floor_demand_weight": st.column_config.NumberColumn("Coverage floor", format="%.0f"),
            "total_candidate_cost": st.column_config.NumberColumn("Cost proxy", format="%.0f"),
            "improvement_vs_baseline_pct": st.column_config.NumberColumn("Coverage uplift", format="%.1%"),
            "cost_saving_vs_baseline_pct": st.column_config.NumberColumn("Cost-floor saving", format="%.1%"),
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
    method_diagnostics = optimization_diagnostics[
        (optimization_diagnostics["scenario_id"] == selected_scenario)
        & (optimization_diagnostics["method_id"] == method_id)
    ].copy()
    st.subheader("Optimization Feasibility")
    if not method_diagnostics.empty:
        pass_count = int((method_diagnostics["constraint_status"] == "pass").sum())
        st.caption(f"{pass_count}/{len(method_diagnostics)} constraints pass for the selected scenario and method.")
        diagnostic_cols = ["constraint_name", "constraint_status", "lhs_value", "operator", "rhs_value", "slack_value", "diagnostic_note"]
        st.dataframe(
            method_diagnostics[diagnostic_cols],
            width="stretch",
            hide_index=True,
            column_config={
                "constraint_name": "Constraint",
                "constraint_status": "Status",
                "lhs_value": st.column_config.NumberColumn("LHS", format="%.3f"),
                "rhs_value": st.column_config.NumberColumn("RHS", format="%.3f"),
                "slack_value": st.column_config.NumberColumn("Slack", format="%.3f"),
                "diagnostic_note": "Diagnostic note",
            },
        )
    else:
        st.info("No constraint diagnostics are available for this scenario and method.")
    country_rows = country_diagnostics[
        (country_diagnostics["scenario_id"] == selected_scenario)
        & (country_diagnostics["method_id"] == method_id)
    ].copy()
    if not country_rows.empty:
        st.subheader("Country Balance Diagnostic")
        concentration_flags = build_country_concentration_guardrails(country_rows.to_dict("records"))
        flagged_concentration = [row for row in concentration_flags if row["concentration_status"] == "Review"]
        if flagged_concentration:
            flag = flagged_concentration[0]
            st.warning(
                f"Country concentration review: {flag['dominant_country']} represents "
                f"{flag['dominant_country_share']} of traced covered demand for this method. "
                "This is a caveat, not a failed optimization result."
            )
        country_cols = [
            "country_code",
            "selected_candidate_count",
            "covered_zone_count",
            "covered_demand_weight",
            "covered_demand_share_of_method",
            "concentration_status",
            "total_candidate_cost",
            "candidate_cost_share_of_method",
            "concentration_review_note",
            "diagnostic_note",
        ]
        st.dataframe(
            country_rows[country_cols].sort_values("covered_demand_share_of_method", ascending=False),
            width="stretch",
            hide_index=True,
            column_config={
                "country_code": "Country",
                "selected_candidate_count": "Selected sites",
                "covered_zone_count": "Covered zones",
                "covered_demand_weight": st.column_config.NumberColumn("Covered demand proxy", format="%.0f"),
                "covered_demand_share_of_method": st.column_config.NumberColumn("Demand share", format="%.1%"),
                "concentration_status": "Concentration",
                "total_candidate_cost": st.column_config.NumberColumn("Cost proxy", format="%.0f"),
                "candidate_cost_share_of_method": st.column_config.NumberColumn("Cost share", format="%.1%"),
                "concentration_review_note": "Concentration review",
                "diagnostic_note": "Diagnostic note",
            },
        )
    site_rows = selected_sites[(selected_sites["scenario_id"] == selected_scenario) & (selected_sites["method_id"] == method_id)]
    selected_site_cols = ["selection_rank", "candidate_site_id", "country_code", "nuts_id", "site_type", "baseline_rank_within_scenario", "c_j"]
    st.dataframe(
        site_rows[selected_site_cols],
        width="stretch",
        hide_index=True,
        column_config={
            "selection_rank": "Selection rank",
            "candidate_site_id": "Candidate ID",
            "baseline_rank_within_scenario": "Baseline rank",
            "c_j": st.column_config.NumberColumn("Cost proxy", format="%.0f"),
        },
    )
    st.download_button(
        "Download selected sites CSV",
        site_rows[selected_site_cols].to_csv(index=False).encode("utf-8"),
        file_name=f"{selected_scenario.replace(':', '_')}_{method_id.replace(':', '_')}_selected_sites.csv",
        mime="text/csv",
    )
    if not site_rows.empty:
        candidate_ids = site_rows.sort_values("selection_rank")["candidate_site_id"].tolist()
        selected_candidate_id = st.selectbox("Candidate drill-down", candidate_ids)
        trace_for_method = lineage_trace[
            (lineage_trace["scenario_id"] == selected_scenario)
            & (lineage_trace["method_id"] == method_id)
        ] if not lineage_trace.empty else pd.DataFrame()
        drilldown = build_candidate_drilldown(
            selected_candidate_id,
            site_rows.to_dict("records"),
            trace_for_method.to_dict("records"),
        )
        render_candidate_drilldown(drilldown)
        zone_rows = zone_trace[
            (zone_trace["scenario_id"] == selected_scenario)
            & (zone_trace["method_id"] == method_id)
            & (zone_trace["candidate_site_id"] == selected_candidate_id)
        ].sort_values("zone_coverage_rank")
        if not zone_rows.empty:
            st.subheader("Covered Zone Trace")
            zone_cols = ["zone_coverage_rank", "demand_zone_id", "distance_km", "zone_demand_weight", "zone_demand_share_of_candidate"]
            st.dataframe(
                zone_rows[zone_cols].head(25),
                width="stretch",
                hide_index=True,
                column_config={
                    "zone_coverage_rank": "Rank",
                    "demand_zone_id": "Demand zone",
                    "distance_km": st.column_config.NumberColumn("Distance km", format="%.1f"),
                    "zone_demand_weight": st.column_config.NumberColumn("Demand proxy", format="%.0f"),
                    "zone_demand_share_of_candidate": st.column_config.NumberColumn("Share", format="%.1%"),
                },
            )
    if not lineage_trace.empty and method_id == "method:mclp-pulp-cbc":
        st.subheader("Candidate Lineage Trace")
        trace_rows = lineage_trace[
            (lineage_trace["scenario_id"] == selected_scenario)
            & (lineage_trace["method_id"] == method_id)
        ]
        lineage_cols = [
            "selection_rank",
            "candidate_site_id",
            "source_record_id",
            "tile_job_id",
            "country_code",
            "nuts_id",
            "site_type",
            "raw_tag_keys",
            "covered_zone_count",
            "covered_demand_weight",
            "coverage_trace_zone_ids",
        ]
        st.dataframe(
            trace_rows[lineage_cols],
            width="stretch",
            hide_index=True,
            column_config={
                "selection_rank": "Selection rank",
                "candidate_site_id": "Candidate ID",
                "source_record_id": "OSM source",
                "tile_job_id": "Tile job",
                "raw_tag_keys": "OSM tag keys",
                "covered_zone_count": "Covered zones",
                "covered_demand_weight": st.column_config.NumberColumn("Covered demand proxy", format="%.0f"),
                "coverage_trace_zone_ids": "Top covered zones",
            },
        )
    st.caption(
        "Phase 5 uses public POI proxies, straight-line coverage, population demand weights, and unit-cost assumptions. "
        "It is an optimization checkpoint for diligence, not an investment-grade site decision."
    )

with tab_method:
    st.subheader("Methodology")
    st.info(
        "Interview readout: ChargeNet starts with public source governance, builds candidate and demand marts, "
        "scores candidates under multiple assumptions, then uses MILP to test whether a better coverage/cost tradeoff exists."
    )
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
    st.subheader("Metric Glossary")
    st.dataframe(
        pd.DataFrame(build_metric_glossary()),
        width="stretch",
        hide_index=True,
        column_config={
            "metric_key": "Metric key",
            "metric_label": "Metric",
            "plain_english": "Plain English",
            "why_it_matters": "Why it matters",
            "caveat": "Caveat",
        },
    )
    st.subheader("Cost Proxy Explanation")
    st.dataframe(
        pd.DataFrame(cost_proxy_explanation_rows()),
        width="stretch",
        hide_index=True,
        column_config={
            "cost_proxy_driver": "Driver",
            "current_logic": "Current logic",
            "why_included": "Why included",
            "limitation": "Limitation",
        },
    )
    if not release_gate.empty:
        st.subheader("Release Gate")
        passed_count = int((release_gate["gate_status"] == "pass").sum())
        total_count = int(len(release_gate))
        st.info(f"{passed_count}/{total_count} release gates pass for the current capped demo snapshot.")
        st.dataframe(
            release_gate[["gate_name", "gate_status", "blocker_count", "detail"]],
            width="stretch",
            hide_index=True,
            column_config={
                "gate_name": "Gate",
                "gate_status": "Status",
                "blocker_count": st.column_config.NumberColumn("Blockers", format="%.0f"),
                "detail": "Detail",
            },
        )
    if not pipeline_snapshot.empty:
        st.subheader("Pipeline Snapshot")
        if not pipeline_certifications.empty:
            latest_reference = pipeline_certifications.iloc[0]
            status_label = str(latest_reference["certification_status"]).replace("_", " ")
            st.info(
                f"Demo drift reference is {status_label}; "
                f"{int(latest_reference['metric_count'])} monitored pipeline metrics reviewed."
            )
            st.caption(str(latest_reference["certification_note"]))
        snapshot_display = pipeline_snapshot[["metric_name", "metric_value", "metric_unit", "source_table"]].copy()
        st.dataframe(
            snapshot_display,
            width="stretch",
            hide_index=True,
            column_config={
                "metric_name": "Metric",
                "metric_value": st.column_config.NumberColumn("Value", format="%.0f"),
                "metric_unit": "Unit",
                "source_table": "Source layer",
            },
        )
        st.caption("Snapshot metrics are used for drift monitoring between reviewed demo pipeline runs.")
    if not pipeline_drift.empty:
        st.subheader("Snapshot Drift")
        drift_cols = [
            "metric_name",
            "current_metric_value",
            "reference_metric_value",
            "relative_delta_pct",
            "warning_threshold_pct",
            "fail_threshold_pct",
            "drift_status",
        ]
        st.dataframe(
            pipeline_drift[drift_cols],
            width="stretch",
            hide_index=True,
            column_config={
                "metric_name": "Metric",
                "current_metric_value": st.column_config.NumberColumn("Current", format="%.0f"),
                "reference_metric_value": st.column_config.NumberColumn("Reference", format="%.0f"),
                "relative_delta_pct": st.column_config.NumberColumn("Delta", format="%.1%"),
                "warning_threshold_pct": st.column_config.NumberColumn("Warning", format="%.0%"),
                "fail_threshold_pct": st.column_config.NumberColumn("Fail", format="%.0%"),
                "drift_status": "Status",
            },
        )

with tab_coverage:
    st.subheader("Coverage Signal")
    country = load_country_summary()
    st.pyplot(plot_country_summary(country), width="stretch")
    st.caption(
        "A lightweight bar chart is used instead of a choropleth because the public portfolio package "
        "does not ship full GIS polygons or large coverage matrices."
    )
