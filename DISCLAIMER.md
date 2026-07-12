# Disclaimer

**This is a hackathon proof-of-concept built for IDBI Innovate 2026 (Problem Statement 3 —
MSME Financial Health Score). It is not a production system and is not affiliated with,
endorsed by, or an official product of IDBI Bank or any of its subsidiaries.**

## 1. All data is synthetic

Every MSME record in this repository — business profiles, GST filings, UPI transactions,
EPFO contributions, bank balances, loan repayment history, cheque bounces, electricity
consumption, water bills, and fuel-expense logs — is **synthetically generated** by
[`backend/scripts/generate_data.py`](backend/scripts/generate_data.py). No real business,
individual, GSTIN, UDYAM number, PAN, or bank account is represented anywhere in this
codebase or its sample data.

The generator produces 5,000 fictitious MSME profiles (seeded for reproducibility) plus a
12-month monthly time series per MSME, across five alternate-data sources described in the
problem statement:

- **GST (GSTR-3B)** — turnover, filing status, input tax credit ratio
- **UPI** — transaction volume/value, average ticket size, digital transaction ratio,
  payment regularity (always present in the synthetic cohort, per spec)
- **EPFO** — employee headcount trend, contribution regularity
- **Account Aggregator / Banking** — loan repayment status, cheque bounces, cash-flow ratio,
  existing debt, bank balance
- **Utility data** — electricity consumption trend (`electricity_consumption`), water bills
  (`water_bill`, scored only for water-intensive sub-sectors: Textiles, Food Processing,
  Hospitality), and a separate fleet/fuel-expense ledger (`fuel_expense`, scored only for
  Logistics/Trading, where transport spend is a meaningful activity proxy)

About 20% of synthetic MSMEs are deliberately made "sparse" — missing GST, EPFO, and/or
Banking data — specifically to exercise the engine's thin-file handling. This mirrors the
real-world New-to-Credit/New-to-Bank population the tool is designed for, but the specific
records themselves are fabricated for demonstration purposes only.

## 2. The health score is a decision-support signal, not a credit decision

The 0-1000 Financial Health Score, its risk category (Prime/Good/Moderate/Caution), and the
suggested loan amount/rate/tenure returned by `/assess`, `/simulate`, and the health-card
endpoints are outputs of a deterministic, weighted-scoring heuristic
(`backend/scoring/engine.py`) calibrated against synthetic data. They are intended to
illustrate how alternate-data signals *could* feed an underwriting workflow. They are:

- **not** a real credit approval, rejection, or pricing decision,
- **not** validated against real repayment/default outcomes,
- **not** a substitute for a bank's own credit policy, KYC, or regulatory underwriting
  process.

Every API response that exports a health card includes an explicit disclaimer to this effect
(see `/export/{msme_id}` in `backend/app/main.py`).

## 3. No real personal or business data

This repository, its sample CSVs (`backend/data/*.csv`), and its demo UI contain no real
personally identifiable information (PII) and no real business information. Business names
are generated with the `Faker` library's Indian locale; UDYAM numbers, GSTINs-style
identifiers, and financial figures are randomly generated and do not correspond to any real
registration.

## 4. OCEN / ULI framing is illustrative, not a claim of live integration

Where this project or its accompanying presentation materials reference the Open Credit
Enablement Network (OCEN) or the RBI's Unified Lending Interface (ULI), that framing
describes **aspirational integration readiness** — i.e., the shape of a health score that
could plug into an OCEN-style loan service provider (LSP) flow — and **not** a working
integration with any live OCEN/ULI endpoint, and not a claim about any specific number of
lenders, banks, or NBFCs being connected. No code in this repository calls, mocks, or
otherwise integrates with OCEN or ULI infrastructure today.

## 5. Limitation of liability

This software is provided "as is" for hackathon evaluation purposes. The creators accept no
liability for any direct, indirect, incidental, or consequential damages arising from its
use, misuse, or any real-world decision made based on its output.
