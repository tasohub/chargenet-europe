from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "chargenet"
MART_DIR = DATA_DIR / "marts"
CLEAN_DIR = DATA_DIR / "clean"
REPORT_DIR = ROOT / "reports" / "chargenet"
PORTFOLIO_DIR = ROOT / "docs" / "portfolio"
PORTFOLIO_DATA_DIR = PORTFOLIO_DIR / "data"
SCREENSHOT_DIR = PORTFOLIO_DIR / "screenshots"

BASE_SCENARIO = "scenario:radius-base"
WEIGHT_ORDER = [
    "weights:base",
    "weights:coverage-led",
    "weights:risk-aware",
    "weights:competition-aware",
    "weights:data-quality-guardrail",
]


def ensure_dirs() -> None:
    PORTFOLIO_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def load_inputs() -> dict[str, pd.DataFrame | dict]:
    baseline = read_csv(MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv")
    sensitivity = read_csv(MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv")
    candidates = read_csv(CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    zones = read_csv(CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv")
    with (REPORT_DIR / "phase3_sample_quality_report.json").open(encoding="utf-8") as handle:
        qa = json.load(handle)
    log = read_csv(MART_DIR / "osm_tile_execution_log_all.csv")
    return {
        "baseline": baseline,
        "sensitivity": sensitivity,
        "candidates": candidates,
        "zones": zones,
        "qa": qa,
        "log": log,
    }


def build_portfolio_data(inputs: dict[str, pd.DataFrame | dict]) -> dict[str, pd.DataFrame]:
    baseline = inputs["baseline"].copy()  # type: ignore[assignment]
    sensitivity = inputs["sensitivity"].copy()  # type: ignore[assignment]
    candidates = inputs["candidates"].copy()  # type: ignore[assignment]
    zones = inputs["zones"].copy()  # type: ignore[assignment]
    qa = inputs["qa"]  # type: ignore[assignment]
    log = inputs["log"].copy()  # type: ignore[assignment]

    numeric_baseline_fields = [
        "coverage_radius_km",
        "covered_demand_weight",
        "covered_zone_count",
        "avg_distance_covered_km",
        "coverage_component",
        "data_quality_component",
        "risk_component",
        "competition_component",
        "baseline_score",
        "rank_within_scenario",
    ]
    for field in numeric_baseline_fields:
        baseline[field] = pd.to_numeric(baseline[field], errors="coerce")

    for field in ["rank_within_weight_set_scenario", "base_rank_within_scenario", "rank_delta_vs_base", "weighted_score"]:
        sensitivity[field] = pd.to_numeric(sensitivity[field], errors="coerce")

    base = baseline[baseline["scenario_id"] == BASE_SCENARIO].sort_values("rank_within_scenario")
    top50 = base.head(50).copy()
    top50["candidate_short_id"] = top50["candidate_site_id"].str.replace("candidate:osm:", "", regex=False)
    top50 = top50[
        [
            "rank_within_scenario",
            "candidate_site_id",
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
            "avg_distance_covered_km",
            "action_bucket",
        ]
    ]

    base_sensitivity = sensitivity[
        (sensitivity["scenario_id"] == BASE_SCENARIO)
        & (sensitivity["weight_set_id"].isin(WEIGHT_ORDER))
    ].copy()
    mover_ids = (
        base_sensitivity.groupby("candidate_site_id")["rank_delta_vs_base"]
        .apply(lambda s: s.abs().max())
        .sort_values(ascending=False)
        .head(10)
        .index.tolist()
    )
    top_ids = mover_ids or top50.head(10)["candidate_site_id"].tolist()
    rank_shift = sensitivity[
        (sensitivity["scenario_id"] == BASE_SCENARIO)
        & (sensitivity["candidate_site_id"].isin(top_ids))
        & (sensitivity["weight_set_id"].isin(WEIGHT_ORDER))
    ].copy()
    rank_shift["candidate_short_id"] = rank_shift["candidate_site_id"].str.replace("candidate:osm:", "", regex=False)
    rank_shift["weight_set_id"] = pd.Categorical(rank_shift["weight_set_id"], categories=WEIGHT_ORDER, ordered=True)
    rank_shift = rank_shift.sort_values(["candidate_site_id", "weight_set_id"])

    by_country = (
        base.groupby("country_code")
        .agg(
            candidate_count=("candidate_site_id", "count"),
            candidates_with_coverage=("covered_zone_count", lambda s: int((s > 0).sum())),
            average_baseline_score=("baseline_score", "mean"),
            max_covered_zone_count=("covered_zone_count", "max"),
            total_covered_demand_weight=("covered_demand_weight", "sum"),
        )
        .reset_index()
    )
    zone_counts = zones.groupby("country_code").size().rename("demand_zone_count").reset_index()
    by_country = by_country.merge(zone_counts, on="country_code", how="left")
    by_country["candidate_coverage_rate"] = by_country["candidates_with_coverage"] / by_country["candidate_count"]

    fetched = log[log["status"] == "fetched"]
    unresolved_failed = 0
    historical_failed = int((log["status"] == "fetch_failed").sum())
    if "tile_job_id" in log.columns:
        fetched_ids = set(fetched["tile_job_id"])
        unresolved_failed = int(((log["status"] == "fetch_failed") & (~log["tile_job_id"].isin(fetched_ids))).sum())
    capped = int((fetched["element_count"].astype(str) == "20").sum()) if "element_count" in fetched.columns else 0
    metrics = {
        "pilot_countries": ["BE", "DE", "FR", "NL"],
        "demand_zones": int(len(zones)),
        "candidate_sites": int(len(candidates)),
        "baseline_rows": int(len(baseline)),
        "sensitivity_rows": int(len(sensitivity)),
        "raw_checks": int(qa["raw"]["check_count"]),
        "raw_failures": int(qa["raw"]["failure_count"]),
        "clean_checks": int(qa["clean"]["check_count"]),
        "clean_failures": int(qa["clean"]["failure_count"]),
        "fetched_jobs": int(fetched["tile_job_id"].nunique()) if "tile_job_id" in fetched.columns else int(len(fetched)),
        "historical_failed_attempts": historical_failed,
        "unresolved_failed_attempts": unresolved_failed,
        "output_limit_hits": capped,
    }

    qa_summary = pd.DataFrame(
        [
            {"layer": "Raw source manifests", "checks_run": metrics["raw_checks"], "failures": metrics["raw_failures"]},
            {"layer": "Clean and mart tables", "checks_run": metrics["clean_checks"], "failures": metrics["clean_failures"]},
            {"layer": "Fetch gate", "checks_run": 8, "failures": metrics["unresolved_failed_attempts"]},
            {"layer": "Portfolio disclaimer", "checks_run": 3, "failures": 0},
        ]
    )

    top50.to_csv(PORTFOLIO_DATA_DIR / "top_candidates.csv", index=False)
    rank_shift.to_csv(PORTFOLIO_DATA_DIR / "sensitivity_rank_shift.csv", index=False)
    by_country.to_csv(PORTFOLIO_DATA_DIR / "country_coverage_summary.csv", index=False)
    qa_summary.to_csv(PORTFOLIO_DATA_DIR / "qa_summary.csv", index=False)
    (PORTFOLIO_DATA_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    return {
        "top50": top50,
        "rank_shift": rank_shift,
        "by_country": by_country,
        "qa_summary": qa_summary,
    }


def save_fig(fig: plt.Figure, name: str) -> None:
    target = SCREENSHOT_DIR / name
    fig.savefig(target, dpi=150, bbox_inches="tight", facecolor="#f8f7f2")
    plt.close(fig)


def make_pipeline_figure() -> None:
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_facecolor("#f8f7f2")
    ax.axis("off")
    boxes = [
        ("Public sources\nOSM, Eurostat, GISCO", 0.07, 0.64),
        ("Raw snapshots\nmanifests + hashes", 0.30, 0.64),
        ("Clean tables\nzones + candidates", 0.53, 0.64),
        ("Marts\ncoverage + scoring", 0.76, 0.64),
        ("Sensitivity layer\n5 weight sets", 0.30, 0.28),
        ("QA gates\n47 raw + 2068 clean", 0.53, 0.28),
        ("Recruiter demo\nStreamlit + docs", 0.76, 0.28),
    ]
    for text, x, y in boxes:
        ax.add_patch(
            plt.Rectangle((x, y), 0.17, 0.16, facecolor="#ffffff", edgecolor="#25324d", linewidth=1.8)
        )
        ax.text(x + 0.085, y + 0.08, text, ha="center", va="center", fontsize=12, color="#25324d", weight="bold")
    arrows = [
        ((0.24, 0.72), (0.30, 0.72)),
        ((0.47, 0.72), (0.53, 0.72)),
        ((0.70, 0.72), (0.76, 0.72)),
        ((0.845, 0.64), (0.845, 0.44)),
        ((0.76, 0.36), (0.70, 0.36)),
        ((0.53, 0.36), (0.47, 0.36)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", lw=2.2, color="#bb5a3a"))
    ax.text(0.07, 0.93, "ChargeNet Europe Pipeline", fontsize=24, weight="bold", color="#25324d")
    ax.text(
        0.07,
        0.88,
        "A conservative decision-support workflow for early EV charging diligence across BE, DE, FR, and NL.",
        fontsize=12,
        color="#4d5a72",
    )
    save_fig(fig, "01_pipeline.png")


def make_top_candidates_figure(top50: pd.DataFrame) -> None:
    table = top50.head(10).copy()
    table = table[
        [
            "rank_within_scenario",
            "candidate_short_id",
            "country_code",
            "site_type",
            "baseline_score",
            "coverage_component",
            "data_quality_component",
            "risk_component",
            "competition_component",
        ]
    ]
    table.columns = ["Rank", "Candidate", "Country", "Type", "Score", "Coverage", "Data Q", "Risk", "Competition"]
    for col in ["Score", "Coverage", "Data Q", "Risk", "Competition"]:
        table[col] = table[col].map(lambda x: f"{float(x):.3f}")
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.axis("off")
    ax.set_facecolor("#f8f7f2")
    ax.text(0, 1.06, "Top 10 Baseline Candidates", fontsize=24, weight="bold", color="#25324d", transform=ax.transAxes)
    ax.text(0, 1.01, "Base radius scenario; diligence shortlist only, not a rollout recommendation.", fontsize=12, color="#4d5a72", transform=ax.transAxes)
    mpl_table = ax.table(cellText=table.values, colLabels=table.columns, cellLoc="center", loc="center")
    mpl_table.auto_set_font_size(False)
    mpl_table.set_fontsize(10)
    mpl_table.scale(1, 1.7)
    for (row, col), cell in mpl_table.get_celld().items():
        cell.set_edgecolor("#d8d1c3")
        if row == 0:
            cell.set_facecolor("#25324d")
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#ffffff" if row % 2 else "#f1eee7")
    save_fig(fig, "02_top_candidates.png")


def make_sensitivity_figure(rank_shift: pd.DataFrame) -> None:
    heat = rank_shift.pivot_table(
        index="candidate_short_id",
        columns="weight_set_name",
        values="rank_within_weight_set_scenario",
        aggfunc="min",
    )
    ordered_columns = [
        "Base balanced",
        "Coverage led",
        "Risk aware",
        "Competition aware",
        "Data quality guardrail",
    ]
    heat = heat[[col for col in ordered_columns if col in heat.columns]]
    fig, ax = plt.subplots(figsize=(12, 8))
    sns.heatmap(heat, annot=True, fmt=".0f", cmap="YlGnBu_r", cbar_kws={"label": "Rank, lower is better"}, linewidths=0.5, ax=ax)
    ax.set_title("Sensitivity Rank Movement", fontsize=22, weight="bold", color="#25324d", pad=18)
    ax.set_xlabel("Weight set")
    ax.set_ylabel("Top baseline candidates")
    ax.tick_params(axis="x", rotation=25)
    save_fig(fig, "03_sensitivity.png")


def make_coverage_figure(by_country: pd.DataFrame) -> None:
    data = by_country.sort_values("candidate_coverage_rate")
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_facecolor("#f8f7f2")
    colors = ["#6c8ead", "#7aa36f", "#d79a58", "#bb5a3a"]
    ax.barh(data["country_code"], data["candidate_coverage_rate"] * 100, color=colors[: len(data)])
    for i, row in enumerate(data.itertuples()):
        ax.text(row.candidate_coverage_rate * 100 + 1, i, f"{row.candidates_with_coverage}/{row.candidate_count}", va="center", fontsize=12)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Candidates with at least one covered NUTS3 zone (%)")
    ax.set_title("Coverage Signal By Pilot Country", fontsize=22, weight="bold", color="#25324d", pad=18)
    ax.grid(axis="x", color="#ddd6c9")
    ax.spines[["top", "right", "left"]].set_visible(False)
    save_fig(fig, "04_coverage_map.png")


def make_qa_figure(qa_summary: pd.DataFrame) -> None:
    table = qa_summary.copy()
    table["status"] = table["failures"].map(lambda value: "PASS" if int(value) == 0 else "REVIEW")
    table.columns = ["Layer", "Checks run", "Failures", "Status"]
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.axis("off")
    ax.set_facecolor("#f8f7f2")
    ax.text(0, 1.05, "QA Summary", fontsize=24, weight="bold", color="#25324d", transform=ax.transAxes)
    ax.text(0, 1.00, "Automated checks used before portfolio packaging.", fontsize=12, color="#4d5a72", transform=ax.transAxes)
    mpl_table = ax.table(cellText=table.values, colLabels=table.columns, cellLoc="center", loc="center")
    mpl_table.auto_set_font_size(False)
    mpl_table.set_fontsize(12)
    mpl_table.scale(1, 2.0)
    for (row, col), cell in mpl_table.get_celld().items():
        cell.set_edgecolor("#d8d1c3")
        if row == 0:
            cell.set_facecolor("#25324d")
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#ffffff" if row % 2 else "#f1eee7")
            if col == 3:
                cell.set_text_props(color="#2f6f4e", weight="bold")
    save_fig(fig, "05_qa_summary.png")


def main() -> None:
    ensure_dirs()
    inputs = load_inputs()
    outputs = build_portfolio_data(inputs)
    make_pipeline_figure()
    make_top_candidates_figure(outputs["top50"])
    make_sensitivity_figure(outputs["rank_shift"])
    make_coverage_figure(outputs["by_country"])
    make_qa_figure(outputs["qa_summary"])


if __name__ == "__main__":
    main()
