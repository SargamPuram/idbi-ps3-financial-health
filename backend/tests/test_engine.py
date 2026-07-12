"""
Tests for the PS3 scoring engine (backend/scoring/engine.py).

No network calls — everything here exercises pure functions / in-memory pandas
DataFrames, mirroring the synthetic-data shape produced by
scripts/generate_data.py, so tests run standalone without the generated
data/*.csv files.

Two areas are covered:
  1. Boundary-value tests on the bucket-label logic (risk_category_for's
     Prime/Good/Moderate/Caution cutoffs) and the confidence_level_for
     cutoffs (High/Medium/Low), since both are simple threshold functions
     where off-by-one errors are easy to introduce and easy to miss.
  2. Tests of build_features(), the function that actually consumes the
     alternate-data monthly time series (electricity/water/fuel-cost trend
     signals among them) and turns it into the flat features dict the rest
     of the engine scores.
"""

import numpy as np
import pandas as pd
import pytest

from scoring.engine import (
    build_features,
    confidence_level_for,
    risk_category_for,
    score_from_features,
)

N_MONTHS = 12


def make_profile(**overrides):
    profile = {
        "sector": "Manufacturing",
        "sub_sector": "Auto Parts",
        "city_tier": 1,
        "years_in_business": 5,
        "employee_count": 20,
        "has_gst": True,
        "has_epfo": True,
        "has_banking": True,
        "has_utility": True,
        "has_fuel_log": False,
        "existing_debt_amount": 500000.0,
        "bank_balance_avg": 200000.0,
    }
    profile.update(overrides)
    return profile


def make_monthly(electricity=None, water=None, fuel=None):
    """Build a 12-row monthly DataFrame with every column build_features()
    might read, populated with plausible constant/flat values by default so
    individual tests only need to override the column(s) they care about."""
    n = N_MONTHS
    idx = np.arange(1, n + 1)
    if electricity is None:
        electricity = np.full(n, 1000.0)
    if water is None:
        water = np.full(n, 500.0)
    if fuel is None:
        fuel = np.full(n, 3000.0)

    return pd.DataFrame({
        "month_index": idx,
        "gstr3b_turnover": np.full(n, 500000.0),
        "gst_growth_rate": np.concatenate([[0.0], np.full(n - 1, 0.01)]),
        "filing_status": ["On-time"] * n,
        "input_credit_ratio": np.full(n, 0.65),
        "monthly_upi_volume": np.linspace(100, 200, n),
        "monthly_upi_value": np.full(n, 400000.0),
        "avg_ticket_size": np.full(n, 2000.0),
        "payment_regularity_score": np.full(n, 80.0),
        "digital_transaction_ratio": np.full(n, 0.5),
        "employee_count_monthly": np.full(n, 20.0),
        "epfo_contribution_status": ["On-time"] * n,
        "bank_balance": np.full(n, 200000.0),
        "loan_repayment_status": ["On-time"] * n,
        "cheque_bounce_flag": np.zeros(n),
        "cash_flow_ratio": np.full(n, 1.1),
        "electricity_consumption": electricity,
        "water_bill": water,
        "fuel_expense": fuel,
    })


# --------------------------------------------------------------------------
# Boundary-value tests: risk_category_for (Prime/Good/Moderate/Caution)
# --------------------------------------------------------------------------

class TestRiskCategoryBoundaries:
    """RISK_CATEGORIES in scoring/engine.py:
    (800, 1000, "Prime"), (600, 799, "Good"), (400, 599, "Moderate"), (0, 399, "Caution")
    """

    def test_prime_good_boundary(self):
        # 799 is the top of "Good"; 800 is the bottom of "Prime".
        label_below, _ = risk_category_for(799)
        label_at, _ = risk_category_for(800)
        assert label_below == "Good"
        assert label_at == "Prime"

    def test_good_moderate_boundary(self):
        # 599 is the top of "Moderate"; 600 is the bottom of "Good".
        label_below, _ = risk_category_for(599)
        label_at, _ = risk_category_for(600)
        assert label_below == "Moderate"
        assert label_at == "Good"

    def test_moderate_caution_boundary(self):
        # 399 is the top of "Caution"; 400 is the bottom of "Moderate".
        label_below, _ = risk_category_for(399)
        label_at, _ = risk_category_for(400)
        assert label_below == "Caution"
        assert label_at == "Moderate"

    def test_extremes(self):
        assert risk_category_for(0)[0] == "Caution"
        assert risk_category_for(1000)[0] == "Prime"

    @pytest.mark.parametrize("score,expected", [
        (799, "Good"), (800, "Prime"),
        (599, "Moderate"), (600, "Good"),
        (399, "Caution"), (400, "Moderate"),
    ])
    def test_all_boundaries_parametrized(self, score, expected):
        label, _ = risk_category_for(score)
        assert label == expected


# --------------------------------------------------------------------------
# Boundary-value tests: confidence_level_for (High/Medium/Low)
# --------------------------------------------------------------------------

class TestConfidenceLevelBoundaries:
    """confidence_level_for: >=4 sources -> High, >=2 -> Medium, else Low."""

    def test_medium_high_boundary(self):
        assert confidence_level_for(3) == "Medium"
        assert confidence_level_for(4) == "High"

    def test_low_medium_boundary(self):
        assert confidence_level_for(1) == "Low"
        assert confidence_level_for(2) == "Medium"

    def test_extremes(self):
        assert confidence_level_for(0) == "Low"
        assert confidence_level_for(5) == "High"


# --------------------------------------------------------------------------
# build_features(): the function that consumes the alt-data monthly signals
# --------------------------------------------------------------------------

class TestBuildFeaturesAltData:
    def test_electricity_trend_positive_when_rising(self):
        profile = make_profile(has_utility=True)
        rising = np.linspace(800, 1600, N_MONTHS)  # clearly increasing
        monthly = make_monthly(electricity=rising)
        f = build_features(profile, monthly)
        assert f["electricity_trend_slope_pct"] is not None
        assert f["electricity_trend_slope_pct"] > 0

    def test_electricity_trend_negative_when_falling(self):
        profile = make_profile(has_utility=True)
        falling = np.linspace(1600, 800, N_MONTHS)  # clearly decreasing
        monthly = make_monthly(electricity=falling)
        f = build_features(profile, monthly)
        assert f["electricity_trend_slope_pct"] is not None
        assert f["electricity_trend_slope_pct"] < 0

    def test_electricity_trend_absent_when_no_utility_source(self):
        # has_utility=False must suppress the signal entirely, even though the
        # monthly DataFrame still physically contains an electricity column
        # (mirrors generate_data.py, which writes NaN for missing sources but
        # the engine gates on the has_utility flag, not on NaN-sniffing).
        profile = make_profile(has_utility=False)
        rising = np.linspace(800, 1600, N_MONTHS)
        monthly = make_monthly(electricity=rising)
        f = build_features(profile, monthly)
        assert f["electricity_trend_slope_pct"] is None

    def test_water_trend_scored_only_for_water_intensive_subsector(self):
        rising_water = np.linspace(300, 900, N_MONTHS)

        textiles_profile = make_profile(has_utility=True, sector="Manufacturing", sub_sector="Textiles")
        f_textiles = build_features(textiles_profile, make_monthly(water=rising_water))
        assert f_textiles["water_trend_slope_pct"] is not None

        # Auto Parts is not in WATER_INTENSIVE_SUBSECTORS -> water trend must be
        # suppressed even though the underlying data is identical.
        auto_parts_profile = make_profile(has_utility=True, sector="Manufacturing", sub_sector="Auto Parts")
        f_auto = build_features(auto_parts_profile, make_monthly(water=rising_water))
        assert f_auto["water_trend_slope_pct"] is None

    def test_fuel_trend_scored_only_for_relevant_sector_with_fuel_log(self):
        rising_fuel = np.linspace(2000, 6000, N_MONTHS)

        logistics_profile = make_profile(sector="Logistics", has_fuel_log=True)
        f_logistics = build_features(logistics_profile, make_monthly(fuel=rising_fuel))
        assert f_logistics["fuel_trend_slope_pct"] is not None
        assert f_logistics["fuel_trend_slope_pct"] > 0

        # Services is not in FUEL_RELEVANT_SECTORS -> suppressed regardless of has_fuel_log.
        services_profile = make_profile(sector="Services", has_fuel_log=True)
        f_services = build_features(services_profile, make_monthly(fuel=rising_fuel))
        assert f_services["fuel_trend_slope_pct"] is None

        # Logistics but no fuel log present -> suppressed regardless of sector.
        logistics_no_log = make_profile(sector="Logistics", has_fuel_log=False)
        f_no_log = build_features(logistics_no_log, make_monthly(fuel=rising_fuel))
        assert f_no_log["fuel_trend_slope_pct"] is None


# --------------------------------------------------------------------------
# score_from_features(): sanity checks that thin-file MSMEs never get rejected
# --------------------------------------------------------------------------

class TestScoreFromFeaturesThinFile:
    SECTOR_BENCHMARKS = {
        "Manufacturing": {
            "turnover_proxy_avg": {"median": 500000.0, "sorted_values": [200000.0, 400000.0, 500000.0, 600000.0, 800000.0]},
            "employee_count": {"median": 20, "sorted_values": [5, 10, 20, 30, 50]},
            "digital_ratio_avg": {"median": 0.5, "sorted_values": [0.2, 0.4, 0.5, 0.6, 0.8]},
        },
    }

    def test_full_data_msme_gets_high_confidence(self):
        profile = make_profile()
        monthly = make_monthly()
        f = build_features(profile, monthly)
        result = score_from_features(f, self.SECTOR_BENCHMARKS)
        assert result["confidence_level"] == "High"
        assert result["data_completeness_score"] == 100.0
        assert 0 <= result["overall_score"] <= 1000

    def test_thin_file_msme_still_gets_a_score_not_a_rejection(self):
        # Only UPI + utility present -> 2 of 5 core sources -> Medium confidence,
        # but the engine must still return a full score, never a rejection/error.
        profile = make_profile(has_gst=False, has_epfo=False, has_banking=False, has_utility=True)
        monthly = make_monthly()
        f = build_features(profile, monthly)
        result = score_from_features(f, self.SECTOR_BENCHMARKS)
        assert result["overall_score"] is not None
        assert 0 <= result["overall_score"] <= 1000
        assert result["confidence_level"] == "Medium"
        assert result["dimensions"]["revenue_health"]["available"] is False
        assert result["dimensions"]["credit_discipline"]["available"] is False
