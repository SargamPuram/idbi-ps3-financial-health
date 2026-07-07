"""Pydantic request/response models for the PS3 MSME Financial Health API."""

from typing import Optional

from pydantic import BaseModel, Field


class AssessRequest(BaseModel):
    """Submit a new (possibly brand-new-to-bank) MSME for live assessment.
    All data-source blocks are optional/independently omittable — this is the
    thin-file path: omit a whole block (leave has_x=False or its fields None) to
    simulate a MSME missing that data source, exactly like the batch synthetic
    cohort's sparse 20%."""

    business_name: str = "New Applicant"
    sector: str = "Trading"
    sub_sector: Optional[str] = None
    msme_classification: str = "Micro"
    city: str = "Pune"
    city_tier: int = Field(2, ge=1, le=3)
    years_in_business: int = Field(3, ge=0, le=60)
    employee_count: int = Field(5, ge=0, le=2000)

    # --- GST / Revenue Health block ---
    has_gst: bool = True
    avg_monthly_turnover: Optional[float] = 500000
    turnover_growth_rate_avg: Optional[float] = 0.01
    turnover_cv: Optional[float] = 0.20
    filing_ontime_pct: Optional[float] = 80.0
    input_credit_ratio_avg: Optional[float] = 0.65

    # --- EPFO / Operational Health block ---
    has_epfo: bool = True
    employee_growth_rate: Optional[float] = 0.005
    epfo_contribution_regularity_pct: Optional[float] = 80.0

    # --- Utility block (feeds Operational Health) ---
    has_utility: bool = True
    electricity_trend_slope_pct: Optional[float] = 0.005

    # --- Banking / Account Aggregator / Credit Discipline block ---
    has_banking: bool = True
    loan_repayment_ontime_pct: Optional[float] = 80.0
    cheque_bounce_count: Optional[float] = 1
    existing_debt_amount: Optional[float] = 1000000
    cash_flow_adequacy_avg: Optional[float] = 1.1
    bank_balance_avg: Optional[float] = 150000

    # --- UPI / Digital Maturity block (never fully absent, per spec) ---
    upi_volume_growth_rate: float = 0.01
    digital_transaction_ratio_avg: float = 0.5
    payment_regularity_avg: float = 65.0
    avg_ticket_size_growth_rate: float = 0.0

    # --- Turnover proxy override (used for sector benchmark + debt ratio if GST missing) ---
    turnover_proxy_avg: Optional[float] = None


class SimulateRequest(BaseModel):
    msme_id: str
    gst_turnover_increase_pct: float = Field(0.0, description="One-off %% bump to avg monthly GST turnover")
    cheque_bounces_target: Optional[float] = Field(None, description="Directly set annual cheque bounce count")
    employee_growth_increase_pct: float = Field(0.0, description="%% bump to current employee headcount")
    upi_volume_increase_pct: float = Field(0.0, description="%% bump to UPI transaction volume/growth")
