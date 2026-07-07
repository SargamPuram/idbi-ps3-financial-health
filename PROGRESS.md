# PS3 — MSME Financial Health Score — Progress Checkpoint

Read this first if resuming a session. Master index is at `../PROGRESS.md`, full spec at
`../CLAUDE_PROMPTS/02_PS3_FINANCIAL_HEALTH.md`.

Ports: backend 8001, frontend 5174 (see root PROGRESS.md port table — do not collide with PS4 on 8000/5173).

## Status: ✅ DONE (verified by orchestrating session 2026-07-07)

Frontend was actually further along than this file's own checklist indicated when the
background agent was cut off by a session limit — all 5 pages exist and work. Verified live via
headless Playwright across all 5 routes (`/`, `/health-card/MSME00001`, `/simulate`, `/compare`,
`/analytics`) with **zero console/page errors**, plus visually reviewed screenshots — the radar
chart health card (the spec's "star feature") renders correctly with real backend data (score
643/1000, Good, 5-dimensional radar, sub-score breakdown with trend charts). Both servers
confirmed running: backend 8001, frontend 5174.

### Backend
- [x] venv created (py -3.11) at `backend/venv`
- [x] requirements.txt installed (fastapi, uvicorn, pydantic, pandas, numpy, scipy, faker — no
      gradient-boosting libs needed, PS3 is a deterministic weighted-scoring engine per spec)
- [x] `scripts/generate_data.py` — 5,000 MSME synthetic dataset, 60,000 monthly records,
      20.2% sparse (missing >=1 of GST/EPFO/Banking), plus `scripts/score_portfolio.py`
      batch-scores everyone via the shared engine into `data/scored_msmes.csv`.
      Score distribution: mean 625, std 102, range 276-887. Risk categories: Good 56%,
      Moderate 40%, Prime 3.2%, Caution 1%. Confidence: High 88.8%, Medium 11.2%.
- [x] `scoring/engine.py` — shared 5-dimensional scoring engine (build_features +
      score_from_features, used by batch script AND live endpoints)
- [x] `app/main.py` — all 9 FastAPI endpoints implemented
- [x] `app/schemas.py` — Pydantic models (AssessRequest, SimulateRequest)
- [x] All 9 endpoints curl-tested live on port 8001 — all return real, correct data:
      `/`, `/portfolio`, `/health-card/{id}`, `/sector-benchmark/{sector}`, `POST /assess`,
      `POST /simulate`, `/compare?ids=...`, `/analytics`, `/export/{id}`. 404s verified for
      unknown IDs. Fixed a real bug found during testing: `/simulate`'s GST-turnover slider
      wasn't moving the Revenue Health dimension (it only bumped the turnover *level*, not
      the growth-rate feature that dimension is actually scored on) — fixed by also nudging
      `turnover_growth_rate_avg` proportionally.
- [ ] `backend/README.md` written

### Frontend
- [ ] Vite React app scaffolded, port 5174
- [ ] Portfolio Overview page (/)
- [ ] Health Card page (/health-card/:id) — radar chart centerpiece
- [ ] What-If Simulator (/simulate)
- [ ] Compare Mode (/compare)
- [ ] Analytics (/analytics)
- [ ] npm run dev verified loading without console errors

## Design decisions worth recording (so a resuming session doesn't relitigate them)

- **Scoring math reconciling the spec's two weight schemes**: the spec lists each sub-score
  range as "(0-200)" (5 x 200 = 1000, implying equal 20% weight) AND separate explicit
  weights 30/20/25/10/15% (Revenue/Operational/Credit/Digital/Sector). These are
  reconciled as: each sub-score has a **display value 0-200** (raw internal 0-100 pct x 2)
  used for the radar chart / sub-score cards (keeps all radar axes on the same scale), while
  the **contribution to the overall 0-1000 total** uses the explicit weight% (raw_pct/100 *
  weight%/100 * 1000). When all 5 raw_pct = 100, both schemes agree the total is 1000.
- **Which dimensions can be "missing" and trigger weight redistribution**: only Revenue
  Health (needs GST) and Credit Discipline (needs Banking/AA) are ever fully excluded (their
  weight redistributed proportionally to the remaining active dimensions) since those are the
  two sources explicitly named as droppable for the 20% sparse-data cohort. Operational
  Health degrades gracefully (still computable from years-in-business alone even if EPFO AND
  utility are both missing) and Digital Maturity (UPI) / Sector Benchmark are always
  computable — UPI data is never dropped, and sector benchmark falls back to UPI value as a
  turnover proxy if GST is missing.
- **Data sources counted for confidence_level / data_completeness_score**: GST, UPI, EPFO,
  Banking/AA, Utility (5 total). confidence_level: 4-5 present -> High, 2-3 -> Medium,
  1 -> Low (per spec wording exactly). UPI is always present in synthetic data so minimum is 1.
- **Sector benchmarks are precomputed at data-generation time** into
  `data/sector_benchmarks.json` (percentile distributions of turnover-proxy, employee count,
  digital ratio per sector) so both batch scoring and the live `/assess` endpoint for a
  brand-new MSME can percentile-rank against the same reference distribution (mirrors PS4's
  train/serve consistency pattern).

## How to resume from cold

1. Check which checkboxes above are ticked.
2. `cd ps3-financial-health/backend && ./venv/Scripts/python.exe scripts/generate_data.py`
   regenerates data if missing/stale (check `backend/data/` for `msme_profiles.csv` etc).
3. `./venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8001` to serve.
4. Frontend: `cd ps3-financial-health/frontend && npm install && npm run dev -- --port 5174`.
