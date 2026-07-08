"""
Synthetic data generator for PS3 — MSME Financial Health Score.

Generates 5,000 MSME profiles with realistic Indian business data across five
alternate-data sources (GST, UPI, EPFO, Account Aggregator/Banking, Utility),
12 monthly records each. ~20% of MSMEs are made "sparse" (missing GST and/or
EPFO and/or Banking data) to exercise thin-file handling in the scoring engine.

Outputs (to ../data/):
  msme_profiles.csv     - one row per MSME (static profile + data-availability flags)
  monthly_data.csv       - one row per MSME per month (1-12), wide columns, NaN where a
                           data source is unavailable for that MSME
  sector_benchmarks.json - precomputed percentile distributions per sector, used by the
                           scoring engine (both batch scoring and live /assess) for
                           consistent sector-benchmark percentile ranking

A latent per-MSME "business quality" factor drives several dimension-level quality
factors with substantial independent noise on top (not a single deterministic driver),
so scores correlate sensibly with underlying business health without being a giveaway
from any single input field.
"""

import json
import os
import random
import sys

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
np.random.seed(SEED)
random.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)

N_MSME = 5000
N_MONTHS = 12
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUT_DIR, exist_ok=True)

MONTH_LABELS = pd.date_range("2024-07-01", periods=N_MONTHS, freq="MS").strftime("%Y-%m").tolist()

# --------------------------------------------------------------------------
# Reference lists
# --------------------------------------------------------------------------

SECTORS = ["Manufacturing", "Trading", "Services", "Logistics"]
SECTOR_WEIGHTS = [0.30, 0.35, 0.25, 0.10]

SUB_SECTORS = {
    "Manufacturing": ["Textiles", "Auto Parts", "Food Processing", "Pharma", "Chemicals",
                       "Plastics & Packaging", "Engineering Goods"],
    "Trading": ["Wholesale FMCG", "Electronics Retail", "Building Materials",
                "Agri Commodities", "Apparel Trading", "Hardware & Tools"],
    "Services": ["IT Services", "Healthcare Services", "Education", "Hospitality",
                 "Professional Services", "Repair & Maintenance"],
    "Logistics": ["Freight & Transport", "Warehousing", "Courier Services", "Cold Chain"],
}

MERCHANT_CATEGORY = {  # UPI merchant category code proxy, tied to sub-sector
    "Textiles": "Apparel & Fabric", "Auto Parts": "Automotive", "Food Processing": "Food & Beverage",
    "Pharma": "Healthcare & Pharma", "Chemicals": "Industrial Supplies", "Plastics & Packaging": "Industrial Supplies",
    "Engineering Goods": "Industrial Supplies", "Wholesale FMCG": "Grocery & FMCG",
    "Electronics Retail": "Electronics", "Building Materials": "Construction Materials",
    "Agri Commodities": "Agri Trade", "Apparel Trading": "Apparel & Fabric", "Hardware & Tools": "Hardware",
    "IT Services": "IT & Software", "Healthcare Services": "Healthcare & Pharma", "Education": "Education",
    "Hospitality": "Hospitality & Food", "Professional Services": "Professional Services",
    "Repair & Maintenance": "Repair Services", "Freight & Transport": "Transport & Logistics",
    "Warehousing": "Transport & Logistics", "Courier Services": "Transport & Logistics",
    "Cold Chain": "Transport & Logistics",
}

CITY_TIERS = {
    "Mumbai": 1, "Delhi": 1, "Bangalore": 1, "Chennai": 1, "Kolkata": 1, "Hyderabad": 1,
    "Ahmedabad": 1, "Pune": 1,
    "Jaipur": 2, "Lucknow": 2, "Surat": 2, "Nagpur": 2, "Indore": 2, "Bhopal": 2,
    "Coimbatore": 2, "Vadodara": 2, "Chandigarh": 2, "Kochi": 2,
    "Nashik": 3, "Rajkot": 3, "Varanasi": 3, "Amritsar": 3, "Ranchi": 3, "Jodhpur": 3,
    "Guwahati": 3, "Raipur": 3, "Dehradun": 3, "Siliguri": 3,
}
CITIES = list(CITY_TIERS.keys())
CITY_WEIGHTS = [0.09 if CITY_TIERS[c] == 1 else (0.05 if CITY_TIERS[c] == 2 else 0.03) for c in CITIES]

BUSINESS_SUFFIX = {
    "Textiles": ["Textiles", "Fabrics", "Weaving Mills", "Garments"],
    "Auto Parts": ["Auto Parts", "Auto Components", "Motors", "Auto Industries"],
    "Food Processing": ["Foods", "Agro Foods", "Food Industries", "Snacks"],
    "Pharma": ["Pharma", "Formulations", "Life Sciences", "Healthcare"],
    "Chemicals": ["Chemicals", "Chemical Industries", "Industries"],
    "Plastics & Packaging": ["Plastics", "Packaging Industries", "Polymers"],
    "Engineering Goods": ["Engineering Works", "Industries", "Fabricators"],
    "Wholesale FMCG": ["Trading Co", "General Stores", "Distributors", "Enterprises"],
    "Electronics Retail": ["Electronics", "Electricals", "Digital Store"],
    "Building Materials": ["Building Materials", "Hardware Supplies", "Cement Agency"],
    "Agri Commodities": ["Agro Traders", "Commodities", "Agro Industries"],
    "Apparel Trading": ["Apparels", "Garments Trading", "Fashion House"],
    "Hardware & Tools": ["Hardware Mart", "Tools & Equipment", "Hardware Stores"],
    "IT Services": ["Technologies", "Infotech", "Software Solutions", "IT Services"],
    "Healthcare Services": ["Healthcare", "Diagnostics", "Clinic", "Medicare"],
    "Education": ["Academy", "Institute", "Learning Centre", "Educational Trust"],
    "Hospitality": ["Hospitality", "Caterers", "Restaurant", "Foods & Hospitality"],
    "Professional Services": ["Consultants", "Associates", "Advisory Services"],
    "Repair & Maintenance": ["Repair Services", "Service Centre", "Maintenance Co"],
    "Freight & Transport": ["Transport Co", "Roadways", "Logistics", "Freight Movers"],
    "Warehousing": ["Warehousing Co", "Storage Solutions", "Logistics Park"],
    "Courier Services": ["Courier Services", "Express Cargo", "Parcel Services"],
    "Cold Chain": ["Cold Chain Logistics", "Cold Storage", "Frozen Foods Logistics"],
}

MSME_CLASS = ["Micro", "Small", "Medium"]
MSME_CLASS_WEIGHTS = [0.50, 0.35, 0.15]

# Sub-sectors where water consumption is a genuinely meaningful operational signal
# (dyeing/washing for textiles, wash-down + process water for food processing, guest
# rooms/laundry/kitchens for hospitality) -- named explicitly in the PS-explainer session.
WATER_INTENSIVE_SUBSECTORS = {"Textiles", "Food Processing", "Hospitality"}

# Sectors where fleet/logistics fuel cost is a genuinely meaningful operational signal
# (own or hired transport for goods movement) -- named in the PS-explainer session as
# relevant "for logistics/trading businesses specifically".
FUEL_RELEVANT_SECTORS = {"Logistics", "Trading"}

STATE_CODES = ["MH", "DL", "KA", "TN", "WB", "TG", "GJ", "RJ", "UP", "PB", "MP", "JH", "AS", "CG", "UK"]


def random_udyam():
    return f"UDYAM-{random.choice(STATE_CODES)}-{random.randint(1, 30):02d}-{random.randint(1, 9999999):07d}"


def gen_business_name(sub_sector):
    surname = fake.last_name().replace(".", "")
    suffix = random.choice(BUSINESS_SUFFIX[sub_sector])
    return f"{surname} {suffix}"


def linreg_slope(y):
    n = len(y)
    if n < 2:
        return 0.0
    x = np.arange(n)
    return float(np.polyfit(x, y, 1)[0])


def clip01(x):
    return float(np.clip(x, 0.0, 1.0))


# --------------------------------------------------------------------------
# Main generation loop
# --------------------------------------------------------------------------

profiles = []
monthly_rows = []

for i in range(N_MSME):
    msme_id = f"MSME{i + 1:05d}"

    sector = np.random.choice(SECTORS, p=SECTOR_WEIGHTS)
    sub_sector = random.choice(SUB_SECTORS[sector])
    msme_class = np.random.choice(MSME_CLASS, p=MSME_CLASS_WEIGHTS)
    city = np.random.choice(CITIES, p=np.array(CITY_WEIGHTS) / sum(CITY_WEIGHTS))
    city_tier = CITY_TIERS[city]
    years_in_business = int(np.clip(np.random.exponential(6) + 1, 1, 25))
    owner_name = fake.name()
    business_name = gen_business_name(sub_sector)
    udyam_number = random_udyam()
    merchant_category = MERCHANT_CATEGORY[sub_sector]

    # ---- Latent quality factors (correlated but with real independent noise) ----
    # beta(0.9, 0.9) is mildly U-shaped -> more genuinely-strong and genuinely-weak
    # businesses than a centered normal/beta(2,2), which otherwise crushes everyone
    # toward the portfolio mean once 15-20 quasi-independent signals get averaged.
    true_quality = np.random.beta(0.9, 0.9)
    revenue_q = clip01(0.80 * true_quality + 0.20 * np.random.random())
    ops_q = clip01(0.80 * true_quality + 0.20 * np.random.random())
    credit_q = clip01(0.75 * true_quality + 0.25 * np.random.random())
    digital_q = clip01(0.70 * true_quality + 0.30 * np.random.random())

    # base scale factors by MSME class / sector (bigger business -> bigger absolute numbers)
    class_scale = {"Micro": 1.0, "Small": 4.5, "Medium": 18.0}[msme_class]
    sector_scale = {"Manufacturing": 1.3, "Trading": 1.0, "Services": 0.8, "Logistics": 1.1}[sector]
    base_turnover = np.random.uniform(3, 9) * 1e5 * class_scale * sector_scale  # monthly base ~ lakhs

    # ---- Sparse-data assignment (~20% of MSMEs missing >=1 of GST/EPFO/Banking) ----
    is_sparse = np.random.random() < 0.20
    has_gst, has_epfo, has_banking = True, True, True
    if is_sparse:
        n_missing = np.random.choice([1, 2], p=[0.7, 0.3])
        missing_sources = np.random.choice(["gst", "epfo", "banking"], size=n_missing, replace=False)
        has_gst = "gst" not in missing_sources
        has_epfo = "epfo" not in missing_sources
        has_banking = "banking" not in missing_sources
    # UPI always present. Utility present more often for Manufacturing/Logistics.
    utility_base_p = 0.90 if sector in ("Manufacturing", "Logistics") else 0.45
    has_utility = np.random.random() < utility_base_p

    # ================= GST (12 months) =================
    gst_growth_mean = (revenue_q - 0.5) * 0.035  # -1.75% to +1.75% MoM drift
    seasonal = 0.12 * np.sin(np.linspace(0, 2 * np.pi, N_MONTHS) + np.random.uniform(0, 2 * np.pi))
    turnover_series = []
    t = base_turnover * np.random.uniform(0.85, 1.15)
    for m in range(N_MONTHS):
        t = t * (1 + gst_growth_mean + np.random.normal(0, 0.05))
        turnover_series.append(max(t * (1 + seasonal[m]), 1e4))
    turnover_series = np.array(turnover_series)
    gst_rate = np.random.choice([0.05, 0.12, 0.18, 0.28], p=[0.15, 0.35, 0.4, 0.10])
    gst_paid_series = turnover_series * gst_rate * np.random.uniform(0.85, 1.0, N_MONTHS)
    input_credit_ratio_series = np.clip(np.random.normal(0.55 + 0.25 * revenue_q, 0.10, N_MONTHS), 0.05, 0.98)
    inter_state_ratio_series = np.clip(np.random.normal(0.30, 0.15, N_MONTHS), 0.0, 0.95)
    # filing status: better revenue_q -> more on-time
    filing_p_ontime = 0.35 + 0.63 * revenue_q
    filing_status_series = np.random.choice(
        ["On-time", "Late", "Missed"], size=N_MONTHS,
        p=[filing_p_ontime, (1 - filing_p_ontime) * 0.7, (1 - filing_p_ontime) * 0.3],
    )
    growth_rate_series = np.concatenate([[0.0], np.diff(turnover_series) / np.maximum(turnover_series[:-1], 1)])

    # ================= UPI (12 months, always present) =================
    upi_vol_base = np.random.uniform(80, 400) * class_scale
    upi_growth_mean = (digital_q - 0.5) * 0.05
    upi_vol_series, upi_val_series = [], []
    v = upi_vol_base
    for m in range(N_MONTHS):
        v = v * (1 + upi_growth_mean + np.random.normal(0, 0.06))
        v = max(v, 5)
        upi_vol_series.append(v)
        ticket = base_turnover / max(v, 1) * np.random.uniform(0.7, 1.0)
        upi_val_series.append(v * ticket)
    upi_vol_series = np.array(upi_vol_series)
    upi_val_series = np.array(upi_val_series)
    avg_ticket_series = upi_val_series / np.maximum(upi_vol_series, 1)
    digital_ratio_series = np.clip(np.random.normal(0.35 + 0.5 * digital_q, 0.12, N_MONTHS), 0.03, 0.97)
    payment_regularity_series = np.clip(np.random.normal(45 + 45 * digital_q, 10, N_MONTHS), 5, 100)

    # ================= EPFO =================
    emp_count_now = int(np.clip(np.random.exponential(8) * class_scale / 2 + 1, 1, 500))
    emp_trend_drift = (ops_q - 0.45) * 0.02
    emp_series = []
    e = max(emp_count_now - emp_trend_drift * emp_count_now * N_MONTHS, 1)
    for m in range(N_MONTHS):
        e = max(e * (1 + emp_trend_drift + np.random.normal(0, 0.015)), 1)
        emp_series.append(round(e))
    emp_series = np.array(emp_series, dtype=float)
    contribution_p_ontime = 0.32 + 0.65 * ops_q
    epfo_contrib_series = np.random.choice(
        ["On-time", "Late", "Missed"], size=N_MONTHS,
        p=[contribution_p_ontime, (1 - contribution_p_ontime) * 0.75, (1 - contribution_p_ontime) * 0.25],
    )
    avg_salary_per_employee = float(np.clip(np.random.normal(18000 + 12000 * ops_q, 6000), 8000, 90000))

    # ================= Banking / Account Aggregator =================
    bank_balance_series = np.clip(
        base_turnover * np.random.uniform(0.15, 0.45) * (0.6 + 0.6 * credit_q) *
        (1 + np.random.normal(0, 0.1, N_MONTHS)), 1e4, None,
    )
    repay_p_ontime = 0.28 + 0.68 * credit_q
    loan_repay_series = np.random.choice(
        ["On-time", "Late", "Missed"], size=N_MONTHS,
        p=[repay_p_ontime, (1 - repay_p_ontime) * 0.7, (1 - repay_p_ontime) * 0.3],
    )
    bounce_lambda = max(0.02, (1 - credit_q) * 1.8)
    cheque_bounce_series = np.random.poisson(bounce_lambda / N_MONTHS, N_MONTHS)
    existing_debt_amount = float(base_turnover * 12 * np.random.uniform(0.1, 0.6) * (1.3 - 0.5 * credit_q))
    cash_flow_series = np.clip(np.random.normal(0.9 + 0.6 * credit_q, 0.18, N_MONTHS), 0.4, 2.5)

    # ================= Utility: electricity, water =================
    elec_base = np.random.uniform(500, 8000) * class_scale * (1.5 if sector == "Manufacturing" else 0.6)
    elec_trend_drift = (ops_q - 0.45) * 0.02
    elec_series = []
    x = elec_base
    for m in range(N_MONTHS):
        x = max(x * (1 + elec_trend_drift + np.random.normal(0, 0.04)), 20)
        elec_series.append(x)
    elec_series = np.array(elec_series)

    # Water consumption -- bundled with the same utility-bill data source/has_utility flag
    # as electricity. Only genuinely elevated *and* trend-bearing (correlated with ops_q,
    # same mechanism as electricity) for water-intensive sub-sectors; everyone else still
    # gets a plausible small bill but with essentially no trend signal, so the scoring
    # engine doesn't treat an irrelevant sector's water bill as a meaningful operational cue.
    water_intensive = sub_sector in WATER_INTENSIVE_SUBSECTORS
    water_base = np.random.uniform(300, 2200) * class_scale * (2.6 if water_intensive else 0.7)
    water_trend_drift = ((ops_q - 0.45) * 0.018) if water_intensive else np.random.normal(0, 0.003)
    water_bill_series = []
    w = water_base
    for m in range(N_MONTHS):
        w = max(w * (1 + water_trend_drift + np.random.normal(0, 0.05)), 50)
        water_bill_series.append(w)
    water_bill_series = np.array(water_bill_series)

    # ================= Fuel costs (fleet/logistics diesel-petrol spend) =================
    # Genuinely separate data source from the electricity/water utility bill (e.g. a
    # fleet fuel-card ledger), so it gets its own presence flag rather than riding on
    # has_utility. Present far more often, and at much higher scale, for Logistics/Trading
    # (own or hired transport); rare for Services, occasional for Manufacturing (captive
    # delivery fleet).
    fuel_presence_p = {"Logistics": 0.85, "Trading": 0.55, "Manufacturing": 0.20, "Services": 0.08}[sector]
    has_fuel_log = np.random.random() < fuel_presence_p
    fuel_sector_scale = {"Logistics": 2.5, "Trading": 1.2, "Manufacturing": 0.8, "Services": 0.4}[sector]
    fuel_base = np.random.uniform(2000, 15000) * class_scale * fuel_sector_scale
    fuel_trend_drift = (ops_q - 0.45) * 0.022
    fuel_expense_series = []
    u = fuel_base
    for m in range(N_MONTHS):
        u = max(u * (1 + fuel_trend_drift + np.random.normal(0, 0.05)), 100)
        fuel_expense_series.append(u)
    fuel_expense_series = np.array(fuel_expense_series)

    # Assessment date: spread over the last ~9 months, weighted toward more recent
    # (so "recent assessments" / "monthly volume trend" views look realistic)
    days_ago = int(np.random.exponential(70))
    assessment_date = (pd.Timestamp("2026-07-07") - pd.Timedelta(days=min(days_ago, 270))).date().isoformat()

    # ---- Assemble profile row ----
    profiles.append({
        "msme_id": msme_id,
        "assessment_date": assessment_date,
        "business_name": business_name,
        "udyam_number": udyam_number,
        "owner_name": owner_name,
        "sector": sector,
        "sub_sector": sub_sector,
        "merchant_category": merchant_category,
        "msme_classification": msme_class,
        "city": city,
        "city_tier": city_tier,
        "years_in_business": years_in_business,
        "employee_count": emp_count_now,
        "avg_salary_per_employee": round(avg_salary_per_employee, 2),
        "contribution_regularity": round(float(np.mean(epfo_contrib_series == "On-time")) * 100, 1) if has_epfo else None,
        "bank_balance_avg": round(float(bank_balance_series.mean()), 2) if has_banking else None,
        "cheque_bounce_count": int(cheque_bounce_series.sum()) if has_banking else None,
        "existing_debt_amount": round(existing_debt_amount, 2) if has_banking else None,
        "cash_flow_adequacy": round(float(cash_flow_series.mean()), 3) if has_banking else None,
        "electricity_trend_label": (
            "Growing" if elec_trend_drift > 0.004 else ("Declining" if elec_trend_drift < -0.004 else "Stable")
        ) if has_utility else None,
        "water_trend_label": (
            "Growing" if water_trend_drift > 0.004 else ("Declining" if water_trend_drift < -0.004 else "Stable")
        ) if (has_utility and water_intensive) else None,
        "fuel_trend_label": (
            "Growing" if fuel_trend_drift > 0.004 else ("Declining" if fuel_trend_drift < -0.004 else "Stable")
        ) if has_fuel_log else None,
        "is_water_intensive_subsector": water_intensive,
        "has_gst": has_gst,
        "has_upi": True,
        "has_epfo": has_epfo,
        "has_banking": has_banking,
        "has_utility": has_utility,
        "has_fuel_log": has_fuel_log,
        "_true_quality": round(true_quality, 4),  # kept for internal validation only
    })

    for m in range(N_MONTHS):
        monthly_rows.append({
            "msme_id": msme_id,
            "month_index": m + 1,
            "month_label": MONTH_LABELS[m],
            "gstr3b_turnover": round(turnover_series[m], 2) if has_gst else np.nan,
            "gst_paid": round(gst_paid_series[m], 2) if has_gst else np.nan,
            "input_credit_ratio": round(input_credit_ratio_series[m], 4) if has_gst else np.nan,
            "filing_status": filing_status_series[m] if has_gst else None,
            "inter_state_sales_ratio": round(inter_state_ratio_series[m], 4) if has_gst else np.nan,
            "gst_growth_rate": round(growth_rate_series[m], 4) if has_gst else np.nan,
            "monthly_upi_volume": round(upi_vol_series[m], 1),
            "monthly_upi_value": round(upi_val_series[m], 2),
            "avg_ticket_size": round(avg_ticket_series[m], 2),
            "payment_regularity_score": round(payment_regularity_series[m], 1),
            "digital_transaction_ratio": round(digital_ratio_series[m], 4),
            "employee_count_monthly": int(emp_series[m]) if has_epfo else np.nan,
            "epfo_contribution_status": epfo_contrib_series[m] if has_epfo else None,
            "bank_balance": round(bank_balance_series[m], 2) if has_banking else np.nan,
            "loan_repayment_status": loan_repay_series[m] if has_banking else None,
            "cheque_bounce_flag": int(cheque_bounce_series[m]) if has_banking else np.nan,
            "cash_flow_ratio": round(cash_flow_series[m], 4) if has_banking else np.nan,
            "electricity_consumption": round(elec_series[m], 1) if has_utility else np.nan,
            "water_bill": round(water_bill_series[m], 2) if has_utility else np.nan,
            "fuel_expense": round(fuel_expense_series[m], 2) if has_fuel_log else np.nan,
        })

profiles_df = pd.DataFrame(profiles)
monthly_df = pd.DataFrame(monthly_rows)

profiles_path = os.path.join(OUT_DIR, "msme_profiles.csv")
monthly_path = os.path.join(OUT_DIR, "monthly_data.csv")
profiles_df.to_csv(profiles_path, index=False)
monthly_df.to_csv(monthly_path, index=False)

print(f"Wrote {len(profiles_df)} MSME profiles -> {profiles_path}")
print(f"Wrote {len(monthly_df)} monthly records -> {monthly_path}")
print(f"Sparse MSMEs (missing >=1 of GST/EPFO/Banking): "
      f"{int((~profiles_df[['has_gst','has_epfo','has_banking']].all(axis=1)).sum())} "
      f"({(~profiles_df[['has_gst','has_epfo','has_banking']].all(axis=1)).mean() * 100:.1f}%)")
print(profiles_df[["has_gst", "has_epfo", "has_banking", "has_utility", "has_fuel_log"]].mean())
print(f"Water-intensive sub-sectors (Textiles/Food Processing/Hospitality): "
      f"{int(profiles_df['is_water_intensive_subsector'].sum())} "
      f"({profiles_df['is_water_intensive_subsector'].mean() * 100:.1f}%)")
print("Fuel log presence by sector:")
print(profiles_df.groupby("sector")["has_fuel_log"].mean().round(3))

# --------------------------------------------------------------------------
# Precompute sector benchmark reference distributions
# (turnover-proxy = GST turnover if available else UPI value; employee count;
#  digital transaction ratio) — used by scoring engine for percentile ranking,
# consistent between batch scoring and the live /assess endpoint.
# --------------------------------------------------------------------------

turnover_proxy = monthly_df.groupby("msme_id").apply(
    lambda g: g["gstr3b_turnover"].mean() if g["gstr3b_turnover"].notna().any() else g["monthly_upi_value"].mean()
).rename("turnover_proxy_avg")
digital_ratio_avg = monthly_df.groupby("msme_id")["digital_transaction_ratio"].mean().rename("digital_ratio_avg")

bench_df = profiles_df.set_index("msme_id")[["sector", "employee_count"]].join(turnover_proxy).join(digital_ratio_avg)

sector_benchmarks = {}
for sector, g in bench_df.groupby("sector"):
    sector_benchmarks[sector] = {
        "n": int(len(g)),
        "turnover_proxy_avg": {
            "median": float(g["turnover_proxy_avg"].median()),
            "sorted_values": sorted(round(v, 2) for v in g["turnover_proxy_avg"].tolist()),
        },
        "employee_count": {
            "median": float(g["employee_count"].median()),
            "sorted_values": sorted(int(v) for v in g["employee_count"].tolist()),
        },
        "digital_ratio_avg": {
            "median": float(g["digital_ratio_avg"].median()),
            "sorted_values": sorted(round(v, 4) for v in g["digital_ratio_avg"].tolist()),
        },
    }

bench_path = os.path.join(OUT_DIR, "sector_benchmarks.json")
with open(bench_path, "w") as f:
    json.dump(sector_benchmarks, f, indent=2)
print(f"Wrote sector benchmark reference distributions -> {bench_path}")
