"""
IDBI MSME Health Intelligence — Financial Health Scoring Engine (PS3)

FastAPI serving layer over the shared scoring engine (scoring/engine.py). Loads
the pre-generated synthetic portfolio (5,000 MSMEs, 12-month alternate-data
history per MSME) and the pre-batch-scored health cards on startup. /assess and
/simulate run the SAME engine live for arbitrary/adjusted inputs, so a
batch-scored MSME and a live what-if simulation are always consistent.

Run (from backend/):  uvicorn app.main:app --reload --port 8001
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scoring.engine import build_features, score_from_features, DIMENSION_WEIGHTS, DIMENSION_LABELS
from app.schemas import AssessRequest, SimulateRequest

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

STATE = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading MSME portfolio data...")
    profiles = pd.read_csv(os.path.join(DATA_DIR, "msme_profiles.csv"))
    monthly = pd.read_csv(os.path.join(DATA_DIR, "monthly_data.csv"))
    scored = pd.read_csv(os.path.join(DATA_DIR, "scored_msmes.csv"))
    with open(os.path.join(DATA_DIR, "sector_benchmarks.json")) as f:
        sector_benchmarks = json.load(f)

    full = profiles.merge(scored, on="msme_id", how="left")

    STATE["profiles"] = profiles.set_index("msme_id", drop=False)
    STATE["monthly"] = monthly
    STATE["monthly_by_id"] = {mid: g.sort_values("month_index") for mid, g in monthly.groupby("msme_id")}
    STATE["scored"] = scored.set_index("msme_id", drop=False)
    STATE["full"] = full.set_index("msme_id", drop=False)
    STATE["sector_benchmarks"] = sector_benchmarks
    print(f"Loaded {len(profiles)} MSMEs, {len(monthly)} monthly records. Engine ready.")
    yield
    STATE.clear()


app = FastAPI(
    title="IDBI MSME Health Intelligence — Financial Health Scoring Engine",
    description="5-dimensional (0-1000) MSME Financial Health Score built from alternate "
                 "data (GST, UPI, EPFO, Account Aggregator, Utility) for IDBI Bank (PS3 prototype).",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def get_profile_or_404(msme_id: str) -> dict:
    profiles = STATE["profiles"]
    if msme_id not in profiles.index:
        raise HTTPException(status_code=404, detail=f"MSME '{msme_id}' not found")
    return profiles.loc[msme_id].to_dict()


def get_scored_or_404(msme_id: str) -> dict:
    scored = STATE["scored"]
    if msme_id not in scored.index:
        raise HTTPException(status_code=404, detail=f"MSME '{msme_id}' not scored")
    return scored.loc[msme_id].to_dict()


def get_monthly_or_404(msme_id: str) -> pd.DataFrame:
    m = STATE["monthly_by_id"].get(msme_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"MSME '{msme_id}' has no monthly data")
    return m


def build_features_for(msme_id: str) -> dict:
    profile = get_profile_or_404(msme_id)
    monthly = get_monthly_or_404(msme_id)
    return build_features(profile, monthly)


def dim_summary_from_scored_row(row: dict) -> dict:
    """Reconstruct a compact dimension summary (raw_pct/display/weighted points) from the
    flattened scored_msmes.csv row — used by list-style endpoints (/portfolio, /compare) that
    don't need the full component breakdown."""
    out = {}
    for dim in DIMENSION_WEIGHTS:
        available = bool(row.get(f"{dim}_available"))
        out[dim] = {
            "label": DIMENSION_LABELS[dim],
            "available": available,
            "raw_pct": row.get(f"{dim}_raw_pct") if available else None,
            "display_score": row.get(f"{dim}_display_score") if available else None,
            "weighted_points": row.get(f"{dim}_weighted_points") if available else None,
            "weight_pct": DIMENSION_WEIGHTS[dim],
        }
    return out


def credit_recommendation(overall_score: int, risk_category: str, turnover_proxy_avg: float,
                            existing_debt_amount, confidence_level: str) -> dict:
    annual_turnover = max(turnover_proxy_avg * 12, 1)
    params = {
        "Prime": {"loan_pct": 0.50, "rate_range": (9.5, 10.5), "tenure": 60,
                   "text": "Strong candidate — eligible for premium MSME credit line with minimal collateral."},
        "Good": {"loan_pct": 0.35, "rate_range": (11.0, 12.5), "tenure": 48,
                  "text": "Viable applicant — approve with standard MSME term-loan conditions."},
        "Moderate": {"loan_pct": 0.20, "rate_range": (13.5, 15.0), "tenure": 36,
                      "text": "Approve with enhanced due diligence — consider collateral/guarantor and closer monitoring."},
        "Caution": {"loan_pct": 0.08, "rate_range": (16.0, 18.0), "tenure": 24,
                     "text": "High risk — recommend a secured, smaller-ticket facility with enhanced scrutiny, or refer for restructuring support."},
    }[risk_category]
    suggested_amount = round(annual_turnover * params["loan_pct"], -3)
    if existing_debt_amount:
        suggested_amount = max(suggested_amount - existing_debt_amount * 0.15, annual_turnover * 0.03)
    rate = params["rate_range"][1] - (params["rate_range"][1] - params["rate_range"][0]) * (overall_score % 200) / 200
    return {
        "recommendation_text": params["text"],
        "suggested_loan_amount": round(suggested_amount, -3),
        "suggested_interest_rate_pct": round(rate, 2),
        "suggested_tenure_months": params["tenure"],
        "confidence_pct": {"High": 92, "Medium": 74, "Low": 52}.get(confidence_level, 60),
    }


def monthly_series_for_frontend(monthly: pd.DataFrame) -> dict:
    m = monthly.sort_values("month_index")
    def col(name):
        return [None if pd.isna(v) else (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                for v in m[name]]

    return {
        "months": col("month_label"),
        "gst_turnover_trend": col("gstr3b_turnover"),
        "gst_paid_trend": col("gst_paid"),
        "filing_status": col("filing_status"),
        "input_credit_ratio": col("input_credit_ratio"),
        "employee_count_trend": col("employee_count_monthly"),
        "epfo_contribution_status": col("epfo_contribution_status"),
        "electricity_trend": col("electricity_consumption"),
        "loan_repayment_status": col("loan_repayment_status"),
        "cheque_bounce_flag": col("cheque_bounce_flag"),
        "bank_balance_trend": col("bank_balance"),
        "cash_flow_ratio_trend": col("cash_flow_ratio"),
        "upi_volume_trend": col("monthly_upi_volume"),
        "upi_value_trend": col("monthly_upi_value"),
        "avg_ticket_size_trend": col("avg_ticket_size"),
        "digital_transaction_ratio_trend": col("digital_transaction_ratio"),
        "payment_regularity_trend": col("payment_regularity_score"),
    }


def sector_comparison_for(features: dict) -> list:
    bench = STATE["sector_benchmarks"].get(features["sector"], {})
    rows = []
    mapping = [
        ("turnover_proxy_avg", "Avg monthly turnover (proxy)", features.get("turnover_proxy_avg")),
        ("employee_count", "Employee count", features.get("employee_count")),
        ("digital_ratio_avg", "Digital transaction ratio", features.get("digital_ratio_avg")),
    ]
    for key, label, value in mapping:
        b = bench.get(key, {})
        rows.append({
            "metric": label,
            "this_msme": value,
            "sector_median": b.get("median"),
        })
    return rows


def full_health_card(msme_id: str) -> dict:
    profile = get_profile_or_404(msme_id)
    monthly = get_monthly_or_404(msme_id)
    features = build_features(profile, monthly)
    result = score_from_features(features, STATE["sector_benchmarks"])

    rec = credit_recommendation(
        result["overall_score"], result["risk_category"],
        features["turnover_proxy_avg"], features.get("existing_debt_amount"),
        result["confidence_level"],
    )

    return {
        "msme_id": msme_id,
        "profile": {
            "business_name": profile["business_name"],
            "udyam_number": profile["udyam_number"],
            "owner_name": profile["owner_name"],
            "sector": profile["sector"],
            "sub_sector": profile["sub_sector"],
            "msme_classification": profile["msme_classification"],
            "city": profile["city"],
            "city_tier": int(profile["city_tier"]),
            "years_in_business": int(profile["years_in_business"]),
            "employee_count": int(profile["employee_count"]),
            "assessment_date": profile["assessment_date"],
        },
        "scoring": result,
        "credit_recommendation": rec,
        "monthly_series": monthly_series_for_frontend(monthly),
        "sector_comparison": sector_comparison_for(features),
    }


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "IDBI MSME Health Intelligence — Financial Health Scoring Engine",
        "msmes_loaded": len(STATE["profiles"]) if "profiles" in STATE else 0,
    }


@app.get("/portfolio")
def portfolio_overview():
    full = STATE["full"]

    risk_counts = full["risk_category"].value_counts().to_dict()
    sector_counts = full["sector"].value_counts().to_dict()
    class_counts = full["msme_classification"].value_counts().to_dict()
    city_counts = full["city"].value_counts().to_dict()

    approved = full["risk_category"].isin(["Prime", "Good"]).sum()

    recent = full.sort_values("assessment_date", ascending=False).head(10)
    recent_list = [{
        "msme_id": r["msme_id"], "business_name": r["business_name"], "sector": r["sector"],
        "city": r["city"], "overall_score": int(r["overall_score"]), "risk_category": r["risk_category"],
        "assessment_date": r["assessment_date"],
    } for _, r in recent.iterrows()]

    return {
        "total_msmes_assessed": int(len(full)),
        "average_health_score": round(float(full["overall_score"].mean()), 1),
        "approval_rate_pct": round(float(approved / len(full) * 100), 1),
        "data_completeness_pct": round(float(full["data_completeness_score"].mean()), 1),
        "score_distribution": {k: int(v) for k, v in risk_counts.items()},
        "sector_breakdown": {k: int(v) for k, v in sector_counts.items()},
        "msme_size_distribution": {k: int(v) for k, v in class_counts.items()},
        "geographic_distribution": {k: int(v) for k, v in sorted(city_counts.items(), key=lambda kv: -kv[1])},
        "recent_assessments": recent_list,
    }


@app.get("/health-card/{msme_id}")
def health_card(msme_id: str):
    return full_health_card(msme_id)


@app.get("/sector-benchmark/{sector}")
def sector_benchmark(sector: str):
    bench = STATE["sector_benchmarks"].get(sector)
    if bench is None:
        raise HTTPException(status_code=404, detail=f"No benchmark data for sector '{sector}'")
    full = STATE["full"]
    sector_df = full[full["sector"] == sector]
    if sector_df.empty:
        raise HTTPException(status_code=404, detail=f"No MSMEs found for sector '{sector}'")

    def summary_stats(metric_key):
        vals = bench[metric_key]["sorted_values"]
        n = len(vals)
        return {
            "median": bench[metric_key]["median"],
            "p25": vals[int(n * 0.25)],
            "p75": vals[int(n * 0.75)],
            "min": vals[0],
            "max": vals[-1],
        }

    return {
        "sector": sector,
        "msme_count": int(len(sector_df)),
        "average_health_score": round(float(sector_df["overall_score"].mean()), 1),
        "median_health_score": round(float(sector_df["overall_score"].median()), 1),
        "risk_distribution": {k: int(v) for k, v in sector_df["risk_category"].value_counts().items()},
        "approval_rate_pct": round(float(sector_df["risk_category"].isin(["Prime", "Good"]).mean() * 100), 1),
        "benchmarks": {
            "avg_monthly_turnover_proxy": summary_stats("turnover_proxy_avg"),
            "employee_count": summary_stats("employee_count"),
            "digital_transaction_ratio": summary_stats("digital_ratio_avg"),
        },
        "sub_sector_breakdown": {k: int(v) for k, v in sector_df["sub_sector"].value_counts().items()},
    }


@app.post("/assess")
def assess(req: AssessRequest):
    d = req.model_dump()
    turnover_proxy = d.get("turnover_proxy_avg")
    if turnover_proxy is None:
        if d["has_gst"] and d.get("avg_monthly_turnover") is not None:
            turnover_proxy = d["avg_monthly_turnover"]
        else:
            turnover_proxy = max(d["employee_count"], 1) * 45000  # revenue-per-employee heuristic fallback

    features = {
        "sector": d["sector"], "city_tier": d["city_tier"], "years_in_business": d["years_in_business"],
        "employee_count": d["employee_count"],
        "has_gst": d["has_gst"], "has_upi": True, "has_epfo": d["has_epfo"],
        "has_banking": d["has_banking"], "has_utility": d["has_utility"],
        "turnover_proxy_avg": turnover_proxy,
        "digital_ratio_avg": d["digital_transaction_ratio_avg"],
        "upi_volume_growth_rate": d["upi_volume_growth_rate"],
        "digital_transaction_ratio_avg": d["digital_transaction_ratio_avg"],
        "payment_regularity_avg": d["payment_regularity_avg"],
        "avg_ticket_size_growth_rate": d["avg_ticket_size_growth_rate"],
    }
    if d["has_gst"]:
        features.update({
            "avg_monthly_turnover": d["avg_monthly_turnover"],
            "turnover_growth_rate_avg": d["turnover_growth_rate_avg"],
            "turnover_cv": d["turnover_cv"],
            "filing_ontime_pct": d["filing_ontime_pct"],
            "input_credit_ratio_avg": d["input_credit_ratio_avg"],
        })
    else:
        features.update({k: None for k in
                          ["avg_monthly_turnover", "turnover_growth_rate_avg", "turnover_cv",
                           "filing_ontime_pct", "input_credit_ratio_avg"]})

    if d["has_epfo"]:
        features.update({
            "employee_growth_rate": d["employee_growth_rate"],
            "epfo_contribution_regularity_pct": d["epfo_contribution_regularity_pct"],
        })
    else:
        features.update({"employee_growth_rate": None, "epfo_contribution_regularity_pct": None})

    features["electricity_trend_slope_pct"] = d["electricity_trend_slope_pct"] if d["has_utility"] else None

    if d["has_banking"]:
        features.update({
            "loan_repayment_ontime_pct": d["loan_repayment_ontime_pct"],
            "cheque_bounce_count": d["cheque_bounce_count"],
            "existing_debt_amount": d["existing_debt_amount"],
            "cash_flow_adequacy_avg": d["cash_flow_adequacy_avg"],
            "bank_balance_avg": d["bank_balance_avg"],
            "debt_to_turnover_ratio": (d["existing_debt_amount"] or 0) / max(turnover_proxy * 12, 1),
        })
    else:
        features.update({k: None for k in
                          ["loan_repayment_ontime_pct", "cheque_bounce_count", "existing_debt_amount",
                           "cash_flow_adequacy_avg", "bank_balance_avg", "debt_to_turnover_ratio"]})

    result = score_from_features(features, STATE["sector_benchmarks"])
    rec = credit_recommendation(result["overall_score"], result["risk_category"], turnover_proxy,
                                  features.get("existing_debt_amount"), result["confidence_level"])
    return {
        "input_summary": {"business_name": d["business_name"], "sector": d["sector"], "city": d["city"]},
        "scoring": result,
        "credit_recommendation": rec,
    }


@app.post("/simulate")
def simulate(req: SimulateRequest):
    features = build_features_for(req.msme_id)
    baseline = score_from_features(deepcopy(features), STATE["sector_benchmarks"])

    projected_features = deepcopy(features)
    applied = {}

    if req.gst_turnover_increase_pct and projected_features.get("has_gst"):
        factor = 1 + req.gst_turnover_increase_pct / 100
        projected_features["avg_monthly_turnover"] *= factor
        projected_features["turnover_proxy_avg"] = projected_features["avg_monthly_turnover"]
        # A turnover increase is modeled as being achieved via steady MoM growth, so it also
        # feeds the Revenue Health "growth trend" component (not just the benchmark/debt-ratio level).
        projected_features["turnover_growth_rate_avg"] = (
            (projected_features["turnover_growth_rate_avg"] or 0) + req.gst_turnover_increase_pct / 100 / 12
        )
        if projected_features.get("has_banking") and projected_features.get("existing_debt_amount") is not None:
            projected_features["debt_to_turnover_ratio"] = (
                projected_features["existing_debt_amount"] / max(projected_features["turnover_proxy_avg"] * 12, 1)
            )
        applied["gst_turnover_increase_pct"] = req.gst_turnover_increase_pct

    if req.cheque_bounces_target is not None and projected_features.get("has_banking"):
        projected_features["cheque_bounce_count"] = max(req.cheque_bounces_target, 0)
        applied["cheque_bounces_target"] = req.cheque_bounces_target

    if req.employee_growth_increase_pct:
        projected_features["employee_count"] = max(
            round(projected_features["employee_count"] * (1 + req.employee_growth_increase_pct / 100)), 0
        )
        if projected_features.get("has_epfo") and projected_features.get("employee_growth_rate") is not None:
            projected_features["employee_growth_rate"] += req.employee_growth_increase_pct / 100 / 12
        applied["employee_growth_increase_pct"] = req.employee_growth_increase_pct

    if req.upi_volume_increase_pct:
        projected_features["upi_volume_growth_rate"] += req.upi_volume_increase_pct / 100 / 12
        projected_features["digital_transaction_ratio_avg"] = float(np.clip(
            projected_features["digital_transaction_ratio_avg"] * (1 + req.upi_volume_increase_pct / 200), 0, 1,
        ))
        projected_features["digital_ratio_avg"] = projected_features["digital_transaction_ratio_avg"]
        applied["upi_volume_increase_pct"] = req.upi_volume_increase_pct

    projected = score_from_features(projected_features, STATE["sector_benchmarks"])

    dimension_deltas = {}
    for dim in DIMENSION_WEIGHTS:
        b = baseline["dimensions"][dim]["display_score"]
        p = projected["dimensions"][dim]["display_score"]
        dimension_deltas[dim] = {
            "label": DIMENSION_LABELS[dim],
            "baseline": b,
            "projected": p,
            "delta": round((p or 0) - (b or 0), 1) if b is not None and p is not None else None,
        }

    return {
        "msme_id": req.msme_id,
        "adjustments_applied": applied,
        "current_score": baseline["overall_score"],
        "projected_score": projected["overall_score"],
        "score_delta": projected["overall_score"] - baseline["overall_score"],
        "current_risk_category": baseline["risk_category"],
        "projected_risk_category": projected["risk_category"],
        "dimension_deltas": dimension_deltas,
        "current_scoring": baseline,
        "projected_scoring": projected,
    }


@app.get("/compare")
def compare(ids: str = Query(..., description="Comma-separated MSME IDs, e.g. MSME00001,MSME00002")):
    msme_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if not msme_ids:
        raise HTTPException(status_code=400, detail="Provide at least one MSME id via ?ids=")
    if len(msme_ids) > 5:
        raise HTTPException(status_code=400, detail="Compare supports at most 5 MSMEs at a time")

    cards = []
    for msme_id in msme_ids:
        profile = get_profile_or_404(msme_id)
        row = get_scored_or_404(msme_id)
        features = build_features_for(msme_id)
        rec = credit_recommendation(
            int(row["overall_score"]), row["risk_category"],
            features["turnover_proxy_avg"],
            features.get("existing_debt_amount"), row["confidence_level"],
        )
        cards.append({
            "msme_id": msme_id,
            "business_name": profile["business_name"],
            "sector": profile["sector"],
            "sub_sector": profile["sub_sector"],
            "city": profile["city"],
            "msme_classification": profile["msme_classification"],
            "years_in_business": int(profile["years_in_business"]),
            "employee_count": int(profile["employee_count"]),
            "overall_score": int(row["overall_score"]),
            "risk_category": row["risk_category"],
            "confidence_level": row["confidence_level"],
            "data_completeness_score": row["data_completeness_score"],
            "dimensions": dim_summary_from_scored_row(row),
            "credit_recommendation": rec,
        })

    metrics_table = []
    for dim in DIMENSION_WEIGHTS:
        entry = {"metric": DIMENSION_LABELS[dim]}
        for c in cards:
            entry[c["msme_id"]] = c["dimensions"][dim]["display_score"]
        metrics_table.append(entry)

    return {"msmes": cards, "comparison_table": metrics_table}


@app.get("/analytics")
def analytics():
    full = STATE["full"].copy()

    bins = [0, 200, 400, 600, 800, 1000]
    labels = ["0-200", "200-400", "400-600", "600-800", "800-1000"]
    full["score_bucket"] = pd.cut(full["overall_score"], bins=bins, labels=labels, include_lowest=True)
    score_hist = full["score_bucket"].value_counts().reindex(labels, fill_value=0)

    sector_approval = full.groupby("sector").apply(
        lambda g: round(float(g["risk_category"].isin(["Prime", "Good"]).mean() * 100), 1)
    ).to_dict()

    source_cols = ["has_gst", "has_upi", "has_epfo", "has_banking", "has_utility"]
    completeness = {c.replace("has_", ""): round(float(full[c].mean() * 100), 1) for c in source_cols}
    n_sources = full[source_cols].sum(axis=1)
    thin_file_count = int((n_sources < 3).sum())

    full["assessment_month"] = pd.to_datetime(full["assessment_date"]).dt.to_period("M").astype(str)
    monthly_volume = full.groupby("assessment_month").size().sort_index()

    return {
        "score_distribution_histogram": {k: int(v) for k, v in score_hist.items()},
        "sector_approval_rates_pct": sector_approval,
        "data_completeness_by_source_pct": completeness,
        "thin_file_analysis": {
            "thin_file_count": thin_file_count,
            "thin_file_pct": round(thin_file_count / len(full) * 100, 1),
            "definition": "MSMEs assessed with fewer than 3 of 5 alternate data sources available",
        },
        "monthly_assessment_volume": [{"month": k, "count": int(v)} for k, v in monthly_volume.items()],
        "confidence_level_breakdown": {k: int(v) for k, v in full["confidence_level"].value_counts().items()},
        "average_scores_by_dimension": {
            dim: round(float(full[f"{dim}_display_score"].mean(skipna=True)), 1) for dim in DIMENSION_WEIGHTS
        },
    }


@app.get("/export/{msme_id}")
def export_health_card(msme_id: str):
    card = full_health_card(msme_id)
    return {
        "export_format": "json",
        "generated_for": "IDBI Bank — MSME Credit Assessment (PS3 prototype)",
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "disclaimer": "Synthetic prototype data for hackathon demonstration purposes only. "
                       "Not a real credit decision.",
        "health_card": card,
    }
