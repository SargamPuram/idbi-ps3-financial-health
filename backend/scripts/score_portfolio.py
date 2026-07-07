"""
Batch-scores every MSME in data/msme_profiles.csv using the shared scoring
engine (scoring/engine.py) — the exact same code path the live /assess and
/simulate endpoints use. Writes data/scored_msmes.csv with the overall score,
all 5 dimension scores, risk category, confidence, and JSON-encoded
strengths/weaknesses/suggestions (mirrors ps4-default-prediction's
scored_accounts.csv pattern).

Run after scripts/generate_data.py:
    ./venv/Scripts/python scripts/score_portfolio.py
"""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scoring.engine import build_features, score_from_features

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

print("Loading synthetic MSME dataset...")
profiles = pd.read_csv(os.path.join(DATA_DIR, "msme_profiles.csv"))
monthly = pd.read_csv(os.path.join(DATA_DIR, "monthly_data.csv"))
with open(os.path.join(DATA_DIR, "sector_benchmarks.json")) as fh:
    sector_benchmarks = json.load(fh)

monthly_by_id = {msme_id: g for msme_id, g in monthly.groupby("msme_id")}

rows = []
for _, profile in profiles.iterrows():
    profile_d = profile.to_dict()
    msme_id = profile_d["msme_id"]
    m = monthly_by_id[msme_id]
    features = build_features(profile_d, m)
    result = score_from_features(features, sector_benchmarks)

    row = {
        "msme_id": msme_id,
        "overall_score": result["overall_score"],
        "risk_category": result["risk_category"],
        "risk_category_description": result["risk_category_description"],
        "data_completeness_score": result["data_completeness_score"],
        "confidence_level": result["confidence_level"],
    }
    for dim, out in result["dimensions"].items():
        row[f"{dim}_raw_pct"] = out["raw_pct"]
        row[f"{dim}_display_score"] = out["display_score"]
        row[f"{dim}_weighted_points"] = out["weighted_points"]
        row[f"{dim}_available"] = out["available"]
    row["strengths_json"] = json.dumps(result["strengths"])
    row["weaknesses_json"] = json.dumps(result["weaknesses"])
    row["suggestions_json"] = json.dumps(result["improvement_suggestions"])
    row["data_sources_json"] = json.dumps(result["data_sources"])
    rows.append(row)

scored = pd.DataFrame(rows)
out_path = os.path.join(DATA_DIR, "scored_msmes.csv")
scored.to_csv(out_path, index=False)

print(f"Scored {len(scored)} MSMEs -> {out_path}")
print("\nOverall score distribution:")
print(scored["overall_score"].describe().round(1))
print("\nRisk category counts:")
print(scored["risk_category"].value_counts())
print("\nConfidence level counts:")
print(scored["confidence_level"].value_counts())
print(f"\nMean data completeness: {scored['data_completeness_score'].mean():.1f}%")
