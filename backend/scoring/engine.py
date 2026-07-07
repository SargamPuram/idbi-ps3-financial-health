"""
Shared MSME Financial Health scoring engine — used by BOTH the offline batch
scoring pass (scripts/score_portfolio.py, run at data-generation time) and the
live FastAPI endpoints (/assess, /simulate) in app/main.py, so a batch-scored
MSME and a live what-if simulation go through the exact same math.

Two-stage pipeline (mirrors ps4-default-prediction's feature_engineering.py /
risk_logic.py split):
  1. build_features(profile, monthly_df)  -> flat "features" dict (aggregates
     the 12-month time series into growth rates, ratios, percentages). This is
     the ONLY stage that touches raw monthly rows.
  2. score_from_features(features, sector_benchmarks) -> full health-card dict
     (pure function of the features dict — this is what /assess and /simulate
     call directly with a client-supplied or slider-adjusted features dict).

## Reconciling the two weight schemes in the spec
The spec lists each sub-score range as "(0-200)" (5 x 200 = 1000) but also gives
explicit dimension weights 30/20/25/10/15% that don't map 1:1 onto equal 200-pt
buckets. We resolve this by computing, per dimension, a raw_pct (0-100) driven
by underlying signals, then:
  - display_score (0-200) = raw_pct * 2  -> used for the radar chart / cards,
    keeping every axis on the same 0-200 scale for a visually honest radar.
  - weighted_points = raw_pct/100 * (weight_pct / total_available_weight_pct)
    * 1000 -> this is what actually sums to the 0-1000 overall_score, using
    the spec's explicit weights, renormalized across whichever dimensions are
    actually available for this MSME (weight redistribution on missing data).

Only Revenue Health (needs GST) and Credit Discipline (needs Banking/AA) can
be fully unavailable — those are the two sources the spec names as droppable
for the sparse cohort. Operational Health always resolves (years-in-business
alone is enough if EPFO and utility are both missing) and Digital
Maturity/Sector Benchmark are always available (UPI is never dropped; sector
benchmark falls back to UPI value as a turnover proxy if GST is missing).
"""

import bisect
import math

import numpy as np

DIMENSION_WEIGHTS = {
    "revenue_health": 30,
    "operational_health": 20,
    "credit_discipline": 25,
    "digital_maturity": 10,
    "sector_benchmark": 15,
}
DIMENSION_LABELS = {
    "revenue_health": "Revenue Health",
    "operational_health": "Operational Health",
    "credit_discipline": "Credit Discipline",
    "digital_maturity": "Digital Maturity",
    "sector_benchmark": "Sector Benchmark",
}
CITY_TIER_ADJUSTMENT = {1: 0.0, 2: 4.0, 3: 7.0}

RISK_CATEGORIES = [
    (800, 1000, "Prime", "Strong candidate for lending"),
    (600, 799, "Good", "Viable with standard terms"),
    (400, 599, "Moderate", "Requires additional due diligence"),
    (0, 399, "Caution", "High risk, enhanced scrutiny needed"),
]

FACTOR_LABELS = {
    "revenue_growth": "GST turnover growth trend",
    "revenue_consistency": "Turnover consistency (seasonality/volatility)",
    "revenue_filing": "GST filing compliance",
    "revenue_input_credit": "Input tax credit health",
    "ops_epfo_regularity": "EPFO contribution regularity",
    "ops_employee_growth": "Employee headcount trend",
    "ops_electricity_trend": "Electricity consumption trend",
    "ops_years_stability": "Years-in-business stability",
    "credit_repayment": "Loan repayment history",
    "credit_bounce": "Cheque bounce discipline",
    "credit_debt_ratio": "Debt-to-turnover ratio",
    "credit_cash_flow": "Cash flow adequacy",
    "digital_upi_growth": "UPI transaction volume growth",
    "digital_ratio": "Digital transaction ratio",
    "digital_regularity": "Payment regularity",
    "digital_ticket_stability": "Average ticket size stability",
    "sector_turnover_percentile": "Turnover vs sector peers",
    "sector_employee_percentile": "Employee count vs sector peers",
    "sector_digital_percentile": "Digital adoption vs sector peers",
}

SUGGESTION_TEMPLATES = {
    "revenue_growth": "Grow GSTR-3B turnover more consistently month-on-month",
    "revenue_consistency": "Smooth out revenue volatility across the year (diversify buyer base / staggered billing)",
    "revenue_filing": "Improve GST filing regularity — file GSTR-3B on time every month",
    "revenue_input_credit": "Optimize input tax credit utilization closer to the healthy 55-80% band",
    "ops_epfo_regularity": "Improve EPFO contribution regularity for registered employees",
    "ops_employee_growth": "Stabilize or grow EPFO-registered headcount",
    "ops_electricity_trend": "Stabilize utility consumption — sharp declines can signal reduced production",
    "ops_years_stability": "Continued operating history will steadily improve this factor",
    "credit_repayment": "Improve on-time EMI/loan repayment discipline",
    "credit_bounce": "Reduce cheque bounces — maintain adequate buffer balance before due dates",
    "credit_debt_ratio": "Reduce existing debt relative to turnover, or grow turnover to improve the ratio",
    "credit_cash_flow": "Improve net cash-flow adequacy (inflows vs outflows)",
    "digital_upi_growth": "Grow UPI transaction volume — encourage more digital collections",
    "digital_ratio": "Shift a larger share of transactions from cash to digital/UPI",
    "digital_regularity": "Maintain more regular, predictable payment cycles",
    "digital_ticket_stability": "Stabilize average transaction ticket size",
    "sector_turnover_percentile": "Grow turnover to close the gap with sector-median peers",
    "sector_employee_percentile": "Scale headcount to match sector-median peers",
    "sector_digital_percentile": "Increase digital adoption to match sector-median peers",
}


def _clip01(x):
    return float(np.clip(x, 0.0, 1.0))


def _clip_score(x):
    return float(np.clip(x, 0.0, 100.0))


def linreg_slope(y):
    n = len(y)
    if n < 2:
        return 0.0
    x = np.arange(n)
    return float(np.polyfit(x, y, 1)[0])


def percentile_of(sorted_values, value):
    """Percentile rank (0-100) of `value` within a pre-sorted reference list."""
    n = len(sorted_values)
    if n == 0 or value is None:
        return 50.0
    lo = bisect.bisect_left(sorted_values, value)
    hi = bisect.bisect_right(sorted_values, value)
    rank = (lo + hi) / 2.0
    return float(rank / n * 100)


# --------------------------------------------------------------------------
# Stage 1: feature building from raw monthly time series (batch path)
# --------------------------------------------------------------------------

def build_features(profile: dict, monthly) -> dict:
    """Aggregate a MSME's 12-month time series (a pandas DataFrame, 12 rows,
    sorted or not) plus its static profile dict into the flat features dict
    consumed by score_from_features(). Used for batch scoring of the
    synthetic portfolio."""
    monthly = monthly.sort_values("month_index")
    f = {
        "sector": profile["sector"],
        "city_tier": int(profile["city_tier"]),
        "years_in_business": int(profile["years_in_business"]),
        "employee_count": int(profile["employee_count"]),
        "has_gst": bool(profile["has_gst"]),
        "has_upi": True,
        "has_epfo": bool(profile["has_epfo"]),
        "has_banking": bool(profile["has_banking"]),
        "has_utility": bool(profile["has_utility"]),
    }

    # ---- Revenue Health inputs (GST) ----
    if f["has_gst"]:
        turnover = monthly["gstr3b_turnover"].to_numpy(dtype=float)
        growth = monthly["gst_growth_rate"].to_numpy(dtype=float)[1:]
        f["avg_monthly_turnover"] = float(np.mean(turnover))
        f["turnover_growth_rate_avg"] = float(np.mean(growth)) if len(growth) else 0.0
        f["turnover_cv"] = float(np.std(turnover) / max(np.mean(turnover), 1.0))
        f["filing_ontime_pct"] = float((monthly["filing_status"] == "On-time").mean() * 100)
        f["input_credit_ratio_avg"] = float(monthly["input_credit_ratio"].mean())
    else:
        f.update({"avg_monthly_turnover": None, "turnover_growth_rate_avg": None,
                   "turnover_cv": None, "filing_ontime_pct": None, "input_credit_ratio_avg": None})

    # ---- Turnover proxy for sector benchmark (fallback to UPI value if no GST) ----
    if f["has_gst"]:
        f["turnover_proxy_avg"] = f["avg_monthly_turnover"]
    else:
        f["turnover_proxy_avg"] = float(monthly["monthly_upi_value"].mean())

    # ---- Operational Health inputs (EPFO + utility + years) ----
    if f["has_epfo"]:
        emp = monthly["employee_count_monthly"].to_numpy(dtype=float)
        f["employee_growth_rate"] = linreg_slope(emp) / max(np.mean(emp), 1.0)
        f["epfo_contribution_regularity_pct"] = float((monthly["epfo_contribution_status"] == "On-time").mean() * 100)
    else:
        f["employee_growth_rate"] = None
        f["epfo_contribution_regularity_pct"] = None

    if f["has_utility"]:
        elec = monthly["electricity_consumption"].to_numpy(dtype=float)
        f["electricity_trend_slope_pct"] = linreg_slope(elec) / max(np.mean(elec), 1.0)
    else:
        f["electricity_trend_slope_pct"] = None

    # ---- Credit Discipline inputs (Banking / Account Aggregator) ----
    if f["has_banking"]:
        f["loan_repayment_ontime_pct"] = float((monthly["loan_repayment_status"] == "On-time").mean() * 100)
        f["cheque_bounce_count"] = int(monthly["cheque_bounce_flag"].sum())
        f["existing_debt_amount"] = float(profile["existing_debt_amount"])
        turnover_for_debt = max(f["turnover_proxy_avg"] or 1.0, 1.0)
        f["debt_to_turnover_ratio"] = float(f["existing_debt_amount"] / (turnover_for_debt * 12))
        f["cash_flow_adequacy_avg"] = float(monthly["cash_flow_ratio"].mean())
        f["bank_balance_avg"] = float(profile["bank_balance_avg"])
    else:
        f.update({"loan_repayment_ontime_pct": None, "cheque_bounce_count": None,
                   "existing_debt_amount": None, "debt_to_turnover_ratio": None,
                   "cash_flow_adequacy_avg": None, "bank_balance_avg": None})

    # ---- Digital Maturity inputs (UPI, always present) ----
    upi_vol = monthly["monthly_upi_volume"].to_numpy(dtype=float)
    ticket = monthly["avg_ticket_size"].to_numpy(dtype=float)
    f["upi_volume_growth_rate"] = linreg_slope(upi_vol) / max(np.mean(upi_vol), 1.0)
    f["digital_transaction_ratio_avg"] = float(monthly["digital_transaction_ratio"].mean())
    f["payment_regularity_avg"] = float(monthly["payment_regularity_score"].mean())
    f["avg_ticket_size_growth_rate"] = linreg_slope(ticket) / max(np.mean(ticket), 1.0)
    f["digital_ratio_avg"] = f["digital_transaction_ratio_avg"]

    return f


# --------------------------------------------------------------------------
# Stage 2: dimension scoring (pure functions of the features dict)
# --------------------------------------------------------------------------

def _revenue_health(f):
    if not f.get("has_gst"):
        return None
    growth_score = _clip_score((f["turnover_growth_rate_avg"] + 0.03) / 0.06 * 100)
    consistency_score = _clip_score((1 - (f["turnover_cv"] - 0.05) / 0.55) * 100)
    filing_score = _clip_score(f["filing_ontime_pct"])
    icr = f["input_credit_ratio_avg"]
    icr_score = _clip_score(100 - abs(icr - 0.675) / 0.325 * 100)
    components = {
        "revenue_growth": (growth_score, f["turnover_growth_rate_avg"], "pct_per_month"),
        "revenue_consistency": (consistency_score, f["turnover_cv"], "coefficient_of_variation"),
        "revenue_filing": (filing_score, f["filing_ontime_pct"], "pct"),
        "revenue_input_credit": (icr_score, icr, "ratio"),
    }
    raw = 0.30 * growth_score + 0.25 * consistency_score + 0.30 * filing_score + 0.15 * icr_score
    return raw, components


def _operational_health(f):
    components = {}
    weighted_sum, weight_total = 0.0, 0.0

    years_score = _clip_score(f["years_in_business"] / 15 * 100)
    components["ops_years_stability"] = (years_score, f["years_in_business"], "years")
    weighted_sum += years_score * 0.30
    weight_total += 0.30

    if f.get("has_epfo") and f.get("epfo_contribution_regularity_pct") is not None:
        contrib_score = _clip_score(f["epfo_contribution_regularity_pct"])
        components["ops_epfo_regularity"] = (contrib_score, f["epfo_contribution_regularity_pct"], "pct")
        weighted_sum += contrib_score * 0.35
        weight_total += 0.35

        growth_score = _clip_score((f["employee_growth_rate"] + 0.02) / 0.04 * 100)
        components["ops_employee_growth"] = (growth_score, f["employee_growth_rate"], "pct_per_month")
        weighted_sum += growth_score * 0.25
        weight_total += 0.25

    if f.get("has_utility") and f.get("electricity_trend_slope_pct") is not None:
        elec_score = _clip_score((f["electricity_trend_slope_pct"] + 0.02) / 0.04 * 100)
        components["ops_electricity_trend"] = (elec_score, f["electricity_trend_slope_pct"], "pct_per_month")
        weighted_sum += elec_score * 0.20
        weight_total += 0.20

    raw = weighted_sum / weight_total if weight_total > 0 else years_score
    return raw, components


def _credit_discipline(f):
    if not f.get("has_banking"):
        return None
    repay_score = _clip_score(f["loan_repayment_ontime_pct"])
    bounce_score = _clip_score((1 - f["cheque_bounce_count"] / 6) * 100)
    debt_score = _clip_score((1 - f["debt_to_turnover_ratio"] / 3) * 100)
    cash_score = _clip_score((f["cash_flow_adequacy_avg"] - 0.5) / 1.3 * 100)
    components = {
        "credit_repayment": (repay_score, f["loan_repayment_ontime_pct"], "pct"),
        "credit_bounce": (bounce_score, f["cheque_bounce_count"], "count_per_year"),
        "credit_debt_ratio": (debt_score, f["debt_to_turnover_ratio"], "ratio"),
        "credit_cash_flow": (cash_score, f["cash_flow_adequacy_avg"], "ratio"),
    }
    raw = 0.30 * repay_score + 0.25 * bounce_score + 0.25 * debt_score + 0.20 * cash_score
    return raw, components


def _digital_maturity(f):
    upi_growth_score = _clip_score((f["upi_volume_growth_rate"] + 0.03) / 0.09 * 100)
    digital_ratio_score = _clip_score(f["digital_transaction_ratio_avg"] * 100)
    regularity_score = _clip_score(f["payment_regularity_avg"])
    ticket_stability_score = _clip_score((1 - abs(f["avg_ticket_size_growth_rate"]) / 0.3) * 100)
    components = {
        "digital_upi_growth": (upi_growth_score, f["upi_volume_growth_rate"], "pct_per_month"),
        "digital_ratio": (digital_ratio_score, f["digital_transaction_ratio_avg"], "pct"),
        "digital_regularity": (regularity_score, f["payment_regularity_avg"], "score_0_100"),
        "digital_ticket_stability": (ticket_stability_score, f["avg_ticket_size_growth_rate"], "pct_per_month"),
    }
    raw = 0.30 * upi_growth_score + 0.30 * digital_ratio_score + 0.25 * regularity_score + 0.15 * ticket_stability_score
    return raw, components


def _sector_benchmark(f, sector_benchmarks):
    bench = sector_benchmarks.get(f["sector"])
    if bench is None:
        return 50.0, {}
    turnover_pctl = percentile_of(bench["turnover_proxy_avg"]["sorted_values"], f["turnover_proxy_avg"])
    emp_pctl = percentile_of(bench["employee_count"]["sorted_values"], f["employee_count"])
    digital_pctl = percentile_of(bench["digital_ratio_avg"]["sorted_values"], f["digital_ratio_avg"])
    components = {
        "sector_turnover_percentile": (turnover_pctl, turnover_pctl, "percentile"),
        "sector_employee_percentile": (emp_pctl, emp_pctl, "percentile"),
        "sector_digital_percentile": (digital_pctl, digital_pctl, "percentile"),
    }
    base = (turnover_pctl + emp_pctl + digital_pctl) / 3
    tier_adj = CITY_TIER_ADJUSTMENT.get(f["city_tier"], 0.0)
    raw = _clip_score(base + tier_adj)
    return raw, components


_DIMENSION_FUNCS = {
    "revenue_health": _revenue_health,
    "operational_health": _operational_health,
    "credit_discipline": _credit_discipline,
    "digital_maturity": _digital_maturity,
}


def risk_category_for(score: int):
    for lo, hi, label, desc in RISK_CATEGORIES:
        if lo <= score <= hi:
            return label, desc
    return "Caution", "High risk, enhanced scrutiny needed"


def confidence_level_for(n_sources: int) -> str:
    if n_sources >= 4:
        return "High"
    if n_sources >= 2:
        return "Medium"
    return "Low"


def score_from_features(f: dict, sector_benchmarks: dict) -> dict:
    """Pure function: features dict -> full health-card scoring result.
    This is the single source of truth used by batch scoring, /assess and /simulate."""
    dim_results = {}
    dim_results["revenue_health"] = _revenue_health(f)
    dim_results["operational_health"] = _operational_health(f)
    dim_results["credit_discipline"] = _credit_discipline(f)
    dim_results["digital_maturity"] = _digital_maturity(f)
    dim_results["sector_benchmark"] = _sector_benchmark(f, sector_benchmarks)

    available_dims = {k: v for k, v in dim_results.items() if v is not None}
    total_available_weight = sum(DIMENSION_WEIGHTS[k] for k in available_dims)

    dimensions_out = {}
    overall_score = 0.0
    all_components = {}
    for dim, result in dim_results.items():
        weight_pct = DIMENSION_WEIGHTS[dim]
        if result is None:
            dimensions_out[dim] = {
                "available": False,
                "raw_pct": None,
                "display_score": None,
                "display_max": 200,
                "weight_pct": weight_pct,
                "effective_weight_pct": 0.0,
                "weighted_points": 0.0,
                "components": {},
            }
            continue
        raw_pct, components = result
        raw_pct = _clip_score(raw_pct)
        effective_weight = weight_pct / total_available_weight * 100 if total_available_weight else 0.0
        weighted_points = raw_pct / 100 * effective_weight / 100 * 1000
        overall_score += weighted_points
        dimensions_out[dim] = {
            "available": True,
            "raw_pct": round(raw_pct, 2),
            "display_score": round(raw_pct * 2, 1),
            "display_max": 200,
            "weight_pct": weight_pct,
            "effective_weight_pct": round(effective_weight, 2),
            "weighted_points": round(weighted_points, 2),
            "components": {
                k: {"score": round(v[0], 1), "value": v[1], "unit": v[2], "label": FACTOR_LABELS.get(k, k)}
                for k, v in components.items()
            },
        }
        all_components.update(components)

    overall_score = int(round(np.clip(overall_score, 0, 1000)))
    risk_label, risk_desc = risk_category_for(overall_score)

    sources = ["has_gst", "has_upi", "has_epfo", "has_banking", "has_utility"]
    n_sources_present = sum(1 for s in sources if f.get(s))
    data_completeness_score = round(n_sources_present / len(sources) * 100, 1)
    confidence = confidence_level_for(n_sources_present)

    strengths, weaknesses, suggestions = _explain(all_components, dimensions_out, overall_score)

    return {
        "overall_score": overall_score,
        "risk_category": risk_label,
        "risk_category_description": risk_desc,
        "data_completeness_score": data_completeness_score,
        "confidence_level": confidence,
        "data_sources": {
            "gst": bool(f.get("has_gst")),
            "upi": bool(f.get("has_upi")),
            "epfo": bool(f.get("has_epfo")),
            "account_aggregator": bool(f.get("has_banking")),
            "utility": bool(f.get("has_utility")),
        },
        "dimensions": dimensions_out,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "improvement_suggestions": suggestions,
    }


def _format_value(key, value, unit):
    if value is None:
        return "N/A"
    if unit == "pct" or unit == "percentile":
        return f"{value:.1f}%"
    if unit == "pct_per_month":
        return f"{value * 100:+.2f}%/mo"
    if unit == "ratio":
        return f"{value:.2f}x"
    if unit == "count_per_year":
        return f"{int(value)}/yr"
    if unit == "years":
        return f"{value} yrs"
    if unit == "score_0_100":
        return f"{value:.0f}/100"
    if unit == "coefficient_of_variation":
        return f"{value:.2f} CV"
    return str(value)


def _explain(all_components, dimensions_out, overall_score, top_n=3):
    flat = []
    for key, (score, value, unit) in all_components.items():
        flat.append({"factor": key, "label": FACTOR_LABELS.get(key, key), "score": round(score, 1),
                      "value": value, "display_value": _format_value(key, value, unit)})
    flat.sort(key=lambda r: r["score"], reverse=True)

    strengths = [{"factor": r["factor"], "label": r["label"], "score": r["score"], "value": r["display_value"]}
                 for r in flat[:top_n]]
    weaknesses = [{"factor": r["factor"], "label": r["label"], "score": r["score"], "value": r["display_value"]}
                  for r in flat[-top_n:][::-1]]

    suggestions = []
    for w in weaknesses[:3]:
        factor = w["factor"]
        # find which dimension this factor belongs to, to estimate a realistic point boost
        dim_key = next((d for d, out in dimensions_out.items() if factor in out["components"]), None)
        boost = 0.0
        if dim_key:
            dim = dimensions_out[dim_key]
            # simulate raising this one component's score to 90 (near-ideal), proportional share of dim raw_pct
            n_components = max(len(dim["components"]), 1)
            current_component_score = dim["components"][factor]["score"]
            improvable = max(90 - current_component_score, 0)
            raw_pct_gain = improvable / n_components  # rough proportional contribution
            boost = raw_pct_gain / 100 * dim["effective_weight_pct"] / 100 * 1000
        suggestions.append({
            "factor": factor,
            "suggestion": SUGGESTION_TEMPLATES.get(factor, f"Improve {FACTOR_LABELS.get(factor, factor)}"),
            "estimated_score_gain": round(boost, 1),
            "text": f"{SUGGESTION_TEMPLATES.get(factor, 'Improve ' + FACTOR_LABELS.get(factor, factor))} "
                    f"to boost the health score by an estimated ~{round(boost)} points.",
        })
    return strengths, weaknesses, suggestions
