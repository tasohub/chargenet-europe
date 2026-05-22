# ChargeNet Europe - Completion Gate

## Purpose

The completion gate is the final local check before treating the ChargeNet Europe demo as ready for a public portfolio sync. It wraps the existing release workflow and adds two practical safeguards that matter for a recruiter-facing project: private prep material must stay out of the public surface, and the git worktree must be clean after verification.

Run from the project root:

```powershell
python -m chargenet.cli run-completion-gate
```

The command writes:

```text
reports/chargenet/completion_gate.csv
```

## Gates

| Gate | What it checks | Evidence |
|---|---|---|
| `portfolio_release` | Quality report, public claim scan, release gate, app-data sync, and Streamlit smoke all pass. | `reports/chargenet/portfolio_release_check.csv` |
| `private_boundary` | Private interview-prep files are not listed in public claim paths and `.private/` is ignored. | `.gitignore` |
| `private_history` | Private interview-prep paths are not present in the current branch history being checked. | `git log HEAD -- <path>` |
| `git_worktree` | No uncommitted local changes remain after verification. | `git status --short` |

## Interpretation

A passing completion gate means the local demo state is internally consistent for this checkpoint. It does not mean the project is a production site-selection system. The current ChargeNet Europe scope is still a public-proxy decision-support layer for Belgium, Germany, France, and the Netherlands. It does not model grid capacity, permits, land availability, traffic flows, negotiated CAPEX, or charger utilization.

## Public Sync Note

This gate checks the current working tree and the local branch history. It does not run `git push`, add remotes, or deploy to Streamlit Cloud. If branch history contains earlier private-prep commits, clean the local history deliberately before publishing that branch.
