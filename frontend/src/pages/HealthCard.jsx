import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { endpoints } from "../api/client";
import ScoreGauge from "../components/ScoreGauge";
import HealthRadarChart from "../components/HealthRadarChart";
import SubScoreCard from "../components/SubScoreCard";
import { LoadingSpinner, ErrorBox, RiskBadge, ConfidenceBar, DataSourceChecklist, riskColor } from "../components/Misc";
import { DIMENSION_LABELS } from "../utils/constants";
import { formatINR, formatPct } from "../utils/format";

export default function HealthCard() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [card, setCard] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setCard(null);
    setError(null);
    endpoints
      .healthCard(id)
      .then((res) => setCard(res.data))
      .catch((e) => setError(e.response?.status === 404 ? `MSME '${id}' not found` : e.message));
  }, [id]);

  if (error) return <ErrorBox message={error} />;
  if (!card) return <LoadingSpinner label="Loading health card..." />;

  const { profile, scoring, credit_recommendation, monthly_series, sector_comparison } = card;
  const color = riskColor(scoring.risk_category);

  return (
    <div>
      <div className="flex justify-between items-center" style={{ marginBottom: 18 }}>
        <button className="btn btn-secondary" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <button
          className="btn"
          onClick={() => window.open(`${import.meta.env.VITE_API_BASE_URL || "http://localhost:8001"}/export/${id}`, "_blank")}
        >
          Export JSON
        </button>
      </div>

      {/* Profile header */}
      <div className="card">
        <div className="flex justify-between" style={{ flexWrap: "wrap", gap: 16 }}>
          <div>
            <div className="eyebrow">{profile.udyam_number}</div>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: "0 0 4px" }}>{profile.business_name}</h1>
            <div className="text-muted text-sm">
              Owner: {profile.owner_name} &middot; {profile.sector} / {profile.sub_sector} &middot; {profile.city}
              (Tier {profile.city_tier}) &middot; {profile.years_in_business} yrs in business &middot;{" "}
              {profile.employee_count} employees
            </div>
          </div>
          <div className="flex items-center gap-8">
            <span className="badge badge-neutral">{profile.msme_classification}</span>
            <RiskBadge category={scoring.risk_category} />
          </div>
        </div>
      </div>

      {/* Score + Radar */}
      <div className="grid grid-2 mt-24">
        <div className="card flex flex-col items-center">
          <div className="card-title" style={{ width: "100%" }}>
            Overall Financial Health Score
          </div>
          <ScoreGauge score={scoring.overall_score} riskCategory={scoring.risk_category} />
          <div style={{ marginTop: 14 }}>
            <RiskBadge category={scoring.risk_category} />
          </div>
          <div className="text-sm text-muted mt-8" style={{ textAlign: "center" }}>
            {scoring.risk_category_description}
          </div>
          <div style={{ width: "100%", marginTop: 18 }}>
            <ConfidenceBar level={scoring.confidence_level} completeness={scoring.data_completeness_score} />
          </div>
        </div>

        <div className="card">
          <div className="card-title">5-Dimensional Health Radar</div>
          <HealthRadarChart series={[{ name: "This MSME", color, dimensions: scoring.dimensions }]} />
        </div>
      </div>

      {/* Sub-score cards */}
      <div className="mt-24">
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Sub-Score Breakdown
        </div>
        {Object.entries(DIMENSION_LABELS).map(([key], idx) => (
          <SubScoreCard
            key={key}
            dimKey={key}
            dimData={scoring.dimensions[key]}
            monthlySeries={monthly_series}
            sectorComparison={sector_comparison}
            defaultOpen={idx === 0}
          />
        ))}
      </div>

      {/* Strengths / Weaknesses / Suggestions */}
      <div className="grid grid-3 mt-24">
        <div className="card">
          <div className="card-title">Strengths</div>
          {scoring.strengths.map((s) => (
            <div key={s.factor} className="factor-card strength">
              <span className="factor-icon">✅</span>
              <div>
                <div className="factor-label">{s.label}</div>
                <div className="factor-value">{s.value} &middot; score {s.score.toFixed(0)}/100</div>
              </div>
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-title">Risk Factors</div>
          {scoring.weaknesses.map((w) => (
            <div key={w.factor} className="factor-card weakness">
              <span className="factor-icon">⚠️</span>
              <div>
                <div className="factor-label">{w.label}</div>
                <div className="factor-value">{w.value} &middot; score {w.score.toFixed(0)}/100</div>
              </div>
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-title">AI Improvement Suggestions</div>
          {scoring.improvement_suggestions.map((s) => (
            <div key={s.factor} className="factor-card suggestion">
              <span className="factor-icon">💡</span>
              <div>
                <div className="factor-label">{s.suggestion}</div>
                <div className="factor-value">+{s.estimated_score_gain} points estimated</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Data sources + credit recommendation */}
      <div className="grid grid-2 mt-24">
        <div className="card">
          <div className="card-title">Data Sources</div>
          <DataSourceChecklist sources={scoring.data_sources} />
        </div>
        <div className="card" style={{ borderColor: color, borderWidth: 1.5 }}>
          <div className="card-title">Credit Recommendation</div>
          <div className="fw-700" style={{ fontSize: 15, marginBottom: 10 }}>
            {credit_recommendation.recommendation_text}
          </div>
          <div className="grid grid-3" style={{ gap: 10 }}>
            <div>
              <div className="text-sm text-muted">Suggested Loan Amount</div>
              <div className="fw-700" style={{ fontSize: 17 }}>{formatINR(credit_recommendation.suggested_loan_amount)}</div>
            </div>
            <div>
              <div className="text-sm text-muted">Suggested Interest Rate</div>
              <div className="fw-700" style={{ fontSize: 17 }}>{credit_recommendation.suggested_interest_rate_pct}%</div>
            </div>
            <div>
              <div className="text-sm text-muted">Tenure</div>
              <div className="fw-700" style={{ fontSize: 17 }}>{credit_recommendation.suggested_tenure_months} mo</div>
            </div>
          </div>
          <div className="text-sm text-muted mt-16">
            Model confidence: {formatPct(credit_recommendation.confidence_pct, 0)}
          </div>
        </div>
      </div>
    </div>
  );
}
