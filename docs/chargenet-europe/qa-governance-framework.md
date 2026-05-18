# ChargeNet Europe - QA Governance Framework

## Purpose

This framework defines how specialist QA agents review each phase of the ChargeNet Europe project. The goal is to keep the project rigorous, useful, and portfolio-ready while preventing scope drift, weak assumptions, overclaiming, and generic dashboard output.

QA agents do not implement changes directly. They review phase outputs, cite evidence, assign severity, and decide whether the phase can pass.

## Review Severity

| Severity | Meaning | Phase gate effect |
|---|---|---|
| `P0` | Blocking issue: the phase output is wrong, unsupported, misleading, or not usable by the next phase. | Phase cannot pass. |
| `P1` | Important issue: the phase can proceed only if the issue is fixed before or during the next phase. | Conditional pass. |
| `P2` | Improvement: useful refinement, not blocking. | Phase can pass. |

## Review Output Format

Every QA review must use this structure:

```markdown
# Phase X QA Review

## Reviewed Artifacts

- `path/to/artifact.md`

## Specialist Reviewers

- Reviewer name / role

## Gate Decision

Pass / Conditional Pass / Fail

## Findings

| Severity | Reviewer | Finding | Evidence | Required action |
|---|---|---|---|---|

## Gate Checklist

- [ ] No `P0` findings remain.
- [ ] Every `P1` finding has an owner or next-phase action.
- [ ] Phase acceptance criteria are explicitly checked.
- [ ] Data, model, financial, and business claims are supported by evidence.
```

QA reports should be saved under:

```text
docs/chargenet-europe/qa/phase-X-qa-review.md
```

## Specialist QA Agents

### 1. Strategy Case QA

**Primary phases:** 0, 6, 9, 10

**Required knowledge:**
- Market entry strategy.
- Capital allocation and investment prioritization.
- Target operating model design.
- Value creation and KPI tracking.
- Consulting-style executive communication.

**Checklist:**
- Does the work answer a real business decision?
- Is the target decision-maker clear?
- Does each analytical output map to an action such as build, partner, acquire, wait, monitor, or reject?
- Is the recommendation visible early, not buried in analysis?
- Does the storyline fit strategy, business analytics, and operations roles?

**Red flags:**
- The project reads like an academic model rather than a decision case.
- The problem is framed as "placing chargers" instead of capital allocation.
- Outputs do not support a clear management decision.
- The work overclaims certainty from public data.

### 2. Operations Research QA

**Primary phases:** 1, 4, 5, 6

**Required knowledge:**
- Facility location problem.
- Maximal covering location problem.
- p-median and p-center models.
- MILP formulation and solver diagnostics.
- Multi-objective optimization and NSGA-II.
- Model verification and validation.

**Checklist:**
- Are sets, parameters, variables, objective, and constraints explicit?
- Does the model match the business decision?
- Are feasibility, constraint satisfaction, and objective values reported?
- Is the greedy baseline independent from the optimization output?
- Are scenarios comparable because they use the same candidate sites and demand zones?

**Red flags:**
- A vague weighted score is presented as optimization.
- The objective function mixes incompatible terms without scale control.
- Constraints are not testable.
- Algorithm choice is decorative.
- NSGA-II is introduced before MILP results are stable.

### 3. Data Source QA

**Primary phase:** 2

**Required knowledge:**
- Public data licensing.
- Open Charge Map and OpenStreetMap data limitations.
- EAFO, Eurostat/GISCO, NUTS geography, and population grids.
- Geospatial field requirements.
- Data quality dimensions: accuracy, completeness, consistency, timeliness, validity, uniqueness.

**Checklist:**
- Are source URLs, licenses, fields, refresh cadence, and caveats documented?
- Are sample rows loaded or inspected for each required source?
- Are coordinates, country/region identifiers, charger attributes, and demand-zone fields available?
- Are limitations recorded before modeling starts?
- Is each source fit for its intended use?

**Red flags:**
- Source is cited but not inspectable.
- The project depends on exact utilization or grid capacity without reliable public data.
- Charger location data has no confidence or quality flag.
- Licensing is ignored.

### 4. Data Engineering QA

**Primary phases:** 3, 8

**Required knowledge:**
- Raw, cleaned, and mart data layers.
- Star schema modeling.
- Reproducible data pipelines.
- SQL/DuckDB or SQLite data modeling.
- Data quality reporting.
- Power BI import-friendly exports.

**Checklist:**
- Is there a clean separation between raw, cleaned, and mart datasets?
- Do Power BI and algorithms use the same IDs and definitions?
- Are duplicate, missing, invalid, and inconsistent records handled?
- Can the mart layer be regenerated from documented steps?
- Is the schema simple enough for Power BI without ambiguous many-to-many joins?

**Red flags:**
- Transformations live only inside Power BI with no reproducible upstream logic.
- Business rules are undocumented.
- Many-to-many joins create ambiguous metrics.
- Data quality problems are hidden instead of flagged.

### 5. Baseline And Scoring QA

**Primary phase:** 4

**Required knowledge:**
- Weighted scoring models.
- Sensitivity analysis.
- Business-friendly ranking logic.
- Benchmark design.

**Checklist:**
- Are weights documented and explainable?
- Do top and bottom sites make geographic and business sense?
- Does sensitivity analysis show whether rankings are stable?
- Is the baseline independent enough to compare against MILP?

**Red flags:**
- Scores are arbitrary and cannot be explained.
- Small weight changes completely reverse the recommendation with no discussion.
- The baseline uses information that should only come from the optimization model.

### 6. Experiment Design QA

**Primary phases:** 5, 6

**Required knowledge:**
- Controlled scenario design.
- Sensitivity testing.
- Model comparison.
- Validation metrics for prescriptive analytics.

**Checklist:**
- Are scenarios controlled and comparable?
- Are low/base/high budget and demand assumptions clear?
- Does the experiment show when MILP beats, matches, or loses to baseline?
- Are infeasible scenarios explained rather than hidden?
- Are robust recommendations identified across scenarios?

**Red flags:**
- Only one scenario is shown.
- Algorithms are compared on different inputs.
- Solver results are accepted without checking feasibility.
- The final recommendation depends on one fragile assumption.

### 7. Finance QA

**Primary phase:** 7

**Required knowledge:**
- CAPEX/OPEX modeling.
- Utilization and revenue assumptions.
- Payback and NPV.
- Sensitivity tables.
- Investment memo logic.

**Checklist:**
- Are financial outputs linked to selected site/scenario IDs?
- Are assumptions separated from calculations?
- Can the reviewer change utilization, price, margin, or CAPEX and see outputs update?
- Is the model labeled as assumption-driven rather than investment-grade?
- Are financial metrics used consistently in the deck and Power BI?

**Red flags:**
- Hardcoded outputs.
- Exact ROI claims without data support.
- Finance model is disconnected from optimization results.
- Sensitivity is missing.

### 8. Power BI QA

**Primary phase:** 8

**Required knowledge:**
- Power BI star schema design.
- DAX measure quality.
- Report usability and dashboard design.
- Executive KPI storytelling.
- Refresh and documentation practices.

**Checklist:**
- Does the report answer the case question directly?
- Are pages named by decision purpose?
- Are DAX measures documented and business-readable?
- Do filters and scenarios update outputs coherently?
- Are data limitations visible?
- Are screenshots and refresh instructions exported?

**Red flags:**
- Dashboard is visually busy but does not support a decision.
- Measures are unclear or inconsistent with Excel.
- Report relies on hidden transformations that cannot be reproduced.
- Important caveats are missing.

### 9. Communication And Portfolio QA

**Primary phases:** 9, 10

**Required knowledge:**
- Executive decks.
- Investment memos.
- Recruiter-facing portfolio writing.
- Technical appendix structure.
- Public-safe claims.

**Checklist:**
- Can a recruiter understand the project in 90 seconds?
- Can a technical reviewer reproduce the logic from the appendix?
- Does the CV bullet communicate business value and technical depth?
- Is the recommendation stated before detailed method discussion?
- Are public-data limitations clear?

**Red flags:**
- The deck reads like a school report.
- The README is too technical for HR.
- The public summary overclaims real-world rollout accuracy.
- The project hides assumptions or caveats.

### 10. Overclaim And Ethics QA

**Primary phases:** all phases

**Required knowledge:**
- Assumption labeling.
- Public-data limitations.
- Responsible analytics communication.
- Bias and geographic fairness risks.

**Checklist:**
- Are real data, proxies, and assumptions clearly separated?
- Are limitations visible in every final artifact?
- Are geographic fairness or underserved-region tradeoffs noted where relevant?
- Is the project honest about what public data can and cannot prove?

**Red flags:**
- The project claims exact commercial feasibility.
- Public data is treated as complete ground truth.
- Model recommendations are described as real rollout instructions without diligence.
- Limitations are only hidden in an appendix.

## Phase-To-QA Matrix

| Phase | Required QA reviewers | Gate rule |
|---|---|---|
| Phase 0: Case thesis and scope | Strategy Case QA, Overclaim And Ethics QA | No `P0`; case question, scope, and non-goals must be clear. |
| Phase 1: Literature and method review | Operations Research QA, Strategy Case QA, Overclaim And Ethics QA | No `P0`; method must match the business decision. |
| Phase 2: Data source audit | Data Source QA, Data Engineering QA, Overclaim And Ethics QA | No `P0`; sources must be usable and caveats explicit. |
| Phase 3: Data model and quality layer | Data Engineering QA, Data Source QA, Power BI QA | No `P0`; mart schema must support algorithms and BI. |
| Phase 4: Baseline scoring model | Baseline And Scoring QA, Strategy Case QA, Overclaim And Ethics QA | No `P0`; scoring must be explainable and benchmark-ready. |
| Phase 5: OR MVP | Operations Research QA, Experiment Design QA, Overclaim And Ethics QA | No `P0`; model feasibility and baseline comparison must be shown. |
| Phase 6: Scenario and sensitivity design | Experiment Design QA, Strategy Case QA, Finance QA | No `P0`; recommendation must not depend on one fragile assumption. |
| Phase 7: Excel financial model | Finance QA, Strategy Case QA, Overclaim And Ethics QA | No `P0`; finance must link to scenario outputs and assumptions. |
| Phase 8: Power BI dashboard | Power BI QA, Data Engineering QA, Strategy Case QA | No `P0`; dashboard must answer the case question. |
| Phase 9: Strategy deck and memo | Strategy Case QA, Communication And Portfolio QA, Finance QA | No `P0`; recommendation must be executive-ready. |
| Phase 10: Portfolio packaging | Communication And Portfolio QA, Overclaim And Ethics QA, Strategy Case QA | No `P0`; recruiter and technical reviewer paths must both work. |

## Gate Rule

A phase can pass only when:
- The required QA review file exists.
- No `P0` findings remain.
- All `P1` findings are either fixed or explicitly assigned to the next phase.
- The phase acceptance gate in the master plan is checked.
- Any limitation or assumption created in the phase is carried forward into later artifacts.

## Research Anchors For QA Design

- Data quality dimensions: accuracy, completeness, consistency, timeliness, validity, uniqueness.
- OR verification and validation: separate whether the model is implemented correctly from whether it represents the real decision well.
- Power BI QA: data model quality and decision usefulness matter more than visual polish.
- Analytics lifecycle: problem framing, data, model, implementation, and communication must remain connected.
