# PS3 — IDBI MSME Health Intelligence: Financial Health Scoring Engine (Backend)

A 5-dimensional MSME Financial Health Score (0-1000) built entirely from **alternate data**
(GST, UPI, EPFO, Account Aggregator/Banking, Utility) for IDBI Bank's MSME lending desk —
so New-to-Credit and New-to-Bank enterprises that lack formal balance sheets can still be
underwritten on cash-flow evidence instead of being auto-rejected.

## Why this exists

Only ~41% of registered MSMEs have ever accessed formal credit. Traditional underwriting
needs audited financials most MSMEs don't maintain. This engine fuses 5 alternate-data
sources into one score, **never auto-rejects** (always returns a score + a confidence
indicator, even for thin-file applicants), and is designed for **continuous
post-disbursement monitoring**, not just one-time underwriting — the differentiator versus
incumbents (Perfios, Jocata, FinBox, U GRO) in this space.

## Architecture

```
scripts/generate_data.py   -> synthetic 5,000-MSME dataset: profiles + 12-month time series
                               across GST/UPI/EPFO/Banking/Utility, ~20% deliberately sparse
                               (missing >=1 of GST/EPFO/Banking) to exercise thin-file handling
scripts/score_portfolio.py -> batch-scores the whole portfolio via the shared engine
scoring/engine.py          -> THE scoring engine — build_features() + score_from_features(),
                              used by BOTH the batch script and the live /assess, /simulate
                              endpoints, so results are always consistent
app/schemas.py             -> Pydantic request models (AssessRequest, SimulateRequest)
app/main.py                -> FastAPI serving layer (9 endpoints)
```

## Setup & Run

Requires Python 3.11 (matches the rest of the IDBI Innovate 2026 build; this backend itself
only needs plain scientific-Python, no gradient-boosting libraries, since PS3 is a
deterministic weighted-scoring engine per the spec, not a trained classifier).

```bash
cd ps3-financial-health/backend
py -3.11 -m venv venv
./venv/Scripts/pip install -r requirements.txt      # venv/bin/pip on macOS/Linux

# 1. Generate synthetic MSME dataset (5,000 profiles, 60,000 monthly records, sector benchmarks)
./venv/Scripts/python scripts/generate_data.py

# 2. Batch-score the portfolio through the shared engine
./venv/Scripts/python scripts/score_portfolio.py

# 3. Serve the API
./venv/Scripts/python -m uvicorn app.main:app --reload --port 8001
```

Interactive API docs: http://127.0.0.1:8001/docs

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Health check |
| GET | `/portfolio` | Portfolio summary: totals, score/sector/size/geo distributions, recent assessments |
| GET | `/health-card/{msme_id}` | Full health card: profile, all 5 sub-scores + components, strengths/weaknesses/suggestions, 12-month chart series, sector comparison, credit recommendation |
| GET | `/sector-benchmark/{sector}` | Sector-level averages, risk distribution, benchmark percentile stats |
| POST | `/assess` | Live scoring for a new/arbitrary MSME (JSON body) — supports thin-file inputs by omitting a data-source block |
| POST | `/simulate` | What-if simulator: adjust GST turnover / cheque bounces / employee growth / UPI volume for an existing MSME and see the projected score |
| GET | `/compare?ids=A,B,C` | Side-by-side comparison of up to 5 MSMEs |
| GET | `/analytics` | Score histogram, sector approval rates, data-completeness-by-source, thin-file analysis, monthly assessment volume |
| GET | `/export/{msme_id}` | Structured JSON export of a full health card (for PDF generation downstream) |

## Scoring design notes

- **Reconciling the spec's two weight schemes**: the spec lists each sub-score as
  "(0-200)" (5 x 200 = 1000) but also gives explicit dimension weights
  30/20/25/10/15% (Revenue/Operational/Credit/Digital/Sector) that don't map onto equal
  200-pt buckets. Resolution: each dimension has a **raw_pct (0-100)** computed from its
  underlying signals; the **display_score (0-200)** = raw_pct x 2 is what's shown on the
  radar chart / sub-score cards (keeping every axis on the same scale); the **contribution
  to the 0-1000 overall_score** = raw_pct/100 x effective_weight%/100 x 1000, where
  effective_weight% is the spec's weight renormalized across whichever dimensions are
  actually available for that MSME.
- **Weight redistribution on missing data**: only Revenue Health (needs GST) and Credit
  Discipline (needs Banking/AA) can be fully unavailable — those are the two sources the
  spec names as droppable for the sparse cohort. Operational Health always resolves (falls
  back to years-in-business alone if EPFO and utility are both missing); Digital Maturity
  (UPI) and Sector Benchmark are always available (UPI is never dropped; sector benchmark
  falls back to UPI value as a turnover proxy if GST is missing). The engine **never
  auto-rejects** — a MSME with only 1 data source still gets a full score, just with
  `confidence_level: "Low"`.
- **Confidence & completeness**: `data_completeness_score` = (# of GST/UPI/EPFO/AA/Utility
  present) / 5 x 100. `confidence_level`: 4-5 sources -> High, 2-3 -> Medium, 1 -> Low.
- **Sector benchmarks** are precomputed once at data-generation time into
  `data/sector_benchmarks.json` (sorted reference distributions of turnover-proxy, employee
  count, digital ratio per sector) so both batch scoring and a brand-new live `/assess`
  applicant are percentile-ranked against the exact same reference population — the
  train/serve consistency pattern carried over from PS4.
- **Explainability**: every health card carries top-3 strengths, top-3 weaknesses and 3
  improvement suggestions, each with an **actually-computed** estimated point gain (derived
  by nudging that one underlying factor toward a near-ideal value and re-running the engine
  on the counterfactual, then measuring the overall_score delta) rather than a canned number.
- **Realistic score spread, not a giveaway**: the underlying synthetic "business quality" is
  a mildly U-shaped `beta(0.9, 0.9)` latent factor that drives each dimension's own
  quality factor with substantial independent noise (each dimension keeps 20-30% of its own
  independent randomness on top of the shared factor), and monthly categorical fields
  (filing/repayment/contribution status) are themselves drawn from only 12 binomial trials —
  so scores correlate sensibly with underlying business health without any single input
  field being a deterministic tell. Resulting portfolio: mean ~625, std ~102, range 276-887;
  risk categories Good 55.5%, Moderate 40.2%, Prime 3.3%, Caution 1.0%.
