# ChargeNet Europe - Autonomous Runbook

## Operating Mode

This runbook keeps long autonomous work controlled and context-light. The main agent coordinates, writes durable checkpoints, and verifies outputs. Subagents handle bounded expert reviews or isolated implementation slices.

## Quality Rules

- Do not move to the next phase if open `P0` QA findings remain.
- Every `P1` finding must be fixed or explicitly assigned to the next phase gate.
- Keep all major decisions in files, not only in chat.
- Prefer small reproducible sample ingests before broad downloads.
- Keep public-release safety visible: source attribution, license handling, and proxy/assumption labels.
- Treat outputs as public-data decision-support shortlists, not investment-grade site recommendations.

## Context-Control Rules

- Use concise status updates in chat.
- Store long findings in `docs/chargenet-europe/`.
- Store run checkpoints in `docs/chargenet-europe/run-state.md`.
- Store QA reports under `docs/chargenet-europe/qa/`.
- Subagent outputs are integrated into documents; do not paste full agent output into final summaries unless needed.

## Current Phase Queue

| Order | Phase | Target output | Gate |
|---:|---|---|---|
| 1 | Certified capped MVP snapshot | Keep the latest full rebuild as the current certified decision-support snapshot. | Docs and marts agree; outputs remain labeled capped smoke/batch scope. |
| 2 | Fetch-only OSM expansion windows | Run small resumable Overpass batches without full mart rebuilds. | Lightweight fetch gate passes: unresolved failed attempts `0`, raw/manifest/hash present, no duplicate fetched tile IDs. |
| 3 | Warehouse v2 performance upgrade | Move large compute toward DuckDB/Parquet and sparse coverage facts. | Dense CSV is not the operating store for growing coverage facts. |
| 4 | Milestone certified rebuild | Rebuild clean tables, coverage, baseline, sensitivity, optimization, Power BI exports, data dictionary, and QA only at milestones. | Full `validate`, stale scan, overclaim scan, and specialist QA pass. |
| 5 | Portfolio packaging | BI demo screenshots, case memo, README/deck, QA report. | No open `P0`; no deployment or investment overclaim. |

## Pipeline V2 Run Controls

Do not run the full downstream rebuild after every 9-job fetch batch. Treat the pipeline as two tracks:

- **Fetch-only track:** append immutable OSM raw snapshots and logs, then run lightweight raw/log checks.
- **Certified model track:** rebuild clean/marts/Power BI/docs/QA only at milestones.

Use side-effect-light progress and dry-run commands first:

```powershell
python -m chargenet.cli osm-tile-progress --skip-quality-report
python -m chargenet.cli run-osm-tile-batch --max-jobs 9 --countries BE,DE,FR,NL --extracts charging_stations,candidate_fuel,candidate_services --output-limit 20 --skip-quality-report
```

Use `--execute` only for an intentional live Overpass fetch-only batch:

```powershell
python -m chargenet.cli run-osm-tile-batch --max-jobs 9 --countries BE,DE,FR,NL --extracts charging_stations,candidate_fuel,candidate_services --delay-seconds 2 --output-limit 20 --execute --skip-quality-report
python -m chargenet.cli osm-fetch-gate --latest-only --output-limit 20
python -m chargenet.cli osm-fetch-gate --output-limit 20
```

Both the execute command and the fetch gate must return exit code `0`. If either returns nonzero, stop live fetching and record the hold reason before any retry.

The batch command excludes already fetched tile IDs from `osm_tile_execution_log_all.csv`, so interrupted work can resume from the next remaining planned job. Prefer triplet-friendly batch sizes such as 9, 12, 15, or 24 so charger, fuel, and services extracts stay aligned by tile.

Run the full certified rebuild only at milestones, such as every 90-180 fetched jobs, country completion, 25/50/75/100% progress, model-assumption changes, or before public screenshots/decks:

```powershell
python -m chargenet.cli rebuild-osm-tile-log
python -m chargenet.cli build-osm-tile-smoke-clean
python -m chargenet.cli build-osm-candidate-smoke-clean
python -m chargenet.cli build-tile-smoke-coverage
python -m chargenet.cli build-tile-smoke-scenario-inputs
python -m chargenet.cli build-baseline-scores-tile-smoke
python -m chargenet.cli build-baseline-sensitivity-tile-smoke
python -m chargenet.cli build-optimization-results-tile-smoke
python -m chargenet.cli build-optimization-diagnostics-tile-smoke
python -m chargenet.cli export-powerbi-sample
python -m chargenet.cli write-data-dictionary
python -m chargenet.cli validate
```

Between milestones, keep baseline, sensitivity, optimization, and Power BI outputs labeled with the last certified snapshot. Do not describe fresh fetch-only progress as a current decision model.

## Subagent Pattern

Use xhigh subagents for:
- Architecture review.
- Source ingestion design.
- Optimization-readiness review.
- Overclaim and portfolio QA.
- Later: final Phase 3 specialist QA.

Use the main agent for:
- Integrating results.
- Editing shared files.
- Running verification.
- Keeping scope boundaries.

## Stop Conditions

Stop only if:
- A required source is unavailable and no conservative fallback exists.
- Verification repeatedly fails and needs user choice.
- A QA `P0` cannot be resolved without changing project scope.
- The user returns and redirects the work.
- Any live OSM batch has `failed_jobs > 0`.
- Any live OSM batch receives Overpass `HTTP 429`; pause fetching instead of immediately retrying.
- `osm-fetch-gate` reports missing raw files, missing manifests, manifest hash mismatch, duplicate fetched tile IDs, unknown tile IDs, or nonterminal statuses.
- Public docs drift from capped smoke/batch wording into full-pilot, deployment, investment-grade, or complete-coverage claims.
