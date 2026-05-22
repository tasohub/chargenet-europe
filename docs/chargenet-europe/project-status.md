# ChargeNet Europe - Project Status Report

## Purpose

The project status report is a compact local summary for demo readiness and recruiter-facing review. It collects the current phase, four-country scope, key snapshot metrics, release-gate status, completion-gate status, app fallback file count, and explicit limitations into one CSV.

Run from the project root:

```powershell
python -m chargenet.cli build-project-status
```

The command writes:

```text
reports/chargenet/project_status.csv
```

## What It Reads

| Input | Role |
|---|---|
| `mart_pipeline_snapshot_metrics_tile_smoke.csv` | Candidate, coverage, and optimization snapshot counts. |
| `release_gate_tile_smoke.csv` | Quality, drift, public-claim, app fallback, and manifest gate status. |
| `completion_gate.csv` | Portfolio release, private boundary, private history, and git worktree status. |
| `app_data/manifest.json` | Streamlit Cloud fallback file count. |

## Interpretation

The status report is not another model output. It is an operating summary that helps answer: "What exactly is ready right now, and what are the known boundaries?"

The current status should still be read as a public-proxy Phase 5 MVP for Belgium, Germany, France, and the Netherlands. It does not include grid capacity, permits, land control, traffic flows, negotiated CAPEX, or charger utilization.

## Recommended Use

Run the completion gate first, then build the status report:

```powershell
python -m chargenet.cli run-completion-gate
python -m chargenet.cli build-project-status
```

This keeps the status CSV aligned with the latest release and completion evidence.

