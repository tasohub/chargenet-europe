# ChargeNet Europe - Portfolio Release Check

## Purpose

`run-portfolio-release-check` is the final local gate before treating the current Streamlit demo and app fallback data as recruiter-ready. It does not make the model investment-ready. It checks that the public-data decision-support demo is internally consistent, caveated, and renderable.

Run it from the project root:

```powershell
python -m chargenet.cli run-portfolio-release-check
```

The command writes:

```text
reports/chargenet/portfolio_release_check.csv
```

## Step Order

| Order | Step | What it validates |
|---:|---|---|
| 1 | `quality_report` | Raw and clean/mart data quality checks pass. |
| 2 | `public_claims` | Public-facing ChargeNet text has no unresolved overclaim findings. |
| 3 | `release_gate_pre_sync` | Non-app release gates pass before app fallback refresh. |
| 4 | `app_data_build` | Lightweight `app_data/` CSVs and manifest refresh successfully. |
| 5 | `release_gate_final` | Full release gate passes after app fallback refresh. |
| 6 | `streamlit_smoke` | Streamlit app renders through the test harness with no exceptions. |

If any step fails, later publish/demo steps are marked `skipped`. This prevents a stale app fallback or broken demo from being accidentally treated as ready.

## How To Read The Report

| Field | Meaning |
|---|---|
| `step_order` | Execution order. |
| `step_name` | Release-check step identifier. |
| `step_status` | `pass`, `fail`, or `skipped`. |
| `evidence_path` | File or script used as evidence for the step. |
| `detail` | Short human-readable reason. |

A recruiter-facing demo pass requires every row to be `pass`. A `pass` means the current capped smoke/batch demo is internally consistent; it does not remove the known limitations around incomplete full OSM extraction, public proxy costs, grid capacity, permits, traffic, or land availability.

## Position In The Workflow

Use this command after meaningful model or demo changes:

```powershell
python -m unittest discover -s tests
python -m chargenet.cli run-portfolio-release-check
```

For deeper release work, keep the lower-level commands available:

```powershell
python -m chargenet.cli validate
python -m chargenet.cli build-public-claim-gate
python -m chargenet.cli run-release-gate-tile-smoke
```

The portfolio release check is the top-level convenience command; the lower-level commands remain useful when debugging a specific failed gate.
