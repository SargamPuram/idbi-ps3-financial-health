import { useEffect, useState } from "react";
import { endpoints } from "../api/client";
import HealthRadarChart from "../components/HealthRadarChart";
import { LoadingSpinner, ErrorBox, RiskBadge } from "../components/Misc";
import { DIMENSION_LABELS } from "../utils/constants";
import { formatINR } from "../utils/format";

const OVERLAY_COLORS = ["#14b8a6", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444"];

export default function Compare() {
  const [recentIds, setRecentIds] = useState([]);
  const [selected, setSelected] = useState(["MSME00001", "MSME00002"]);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    endpoints.portfolio().then((res) => setRecentIds(res.data.recent_assessments.map((r) => r.msme_id)));
  }, []);

  const fetchCompare = (ids) => {
    const clean = ids.map((i) => i.trim()).filter(Boolean);
    if (clean.length === 0) return;
    setError(null);
    endpoints
      .compare(clean)
      .then((res) => setData(res.data))
      .catch((e) => setError(e.response?.data?.detail || e.message));
  };

  useEffect(() => {
    fetchCompare(selected);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateSlot = (idx, value) => {
    const next = [...selected];
    next[idx] = value;
    setSelected(next);
  };

  const addSlot = () => {
    if (selected.length >= 5) return;
    setSelected([...selected, ""]);
  };

  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">Side-by-Side Analysis</div>
        <h1>Compare MSMEs</h1>
        <p>Compare up to 5 MSMEs' health cards, radar profiles and credit recommendations side by side.</p>
      </div>

      <div className="card">
        <div className="flex items-center gap-12" style={{ flexWrap: "wrap" }}>
          {selected.map((id, idx) => (
            <input
              key={idx}
              className="input"
              list="recent-msmes-compare"
              value={id}
              onChange={(e) => updateSlot(idx, e.target.value)}
              placeholder={`MSME ID #${idx + 1}`}
              style={{ width: 160 }}
            />
          ))}
          <datalist id="recent-msmes-compare">
            {recentIds.map((rid) => (
              <option key={rid} value={rid} />
            ))}
          </datalist>
          {selected.length < 5 && (
            <button className="btn btn-secondary" onClick={addSlot}>
              + Add MSME
            </button>
          )}
          <button className="btn" onClick={() => fetchCompare(selected)}>
            Compare
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-16">
          <ErrorBox message={error} />
        </div>
      )}
      {!error && !data && <LoadingSpinner label="Loading comparison..." />}

      {data && (
        <>
          <div className="grid mt-24" style={{ gridTemplateColumns: `repeat(${data.msmes.length}, 1fr)` }}>
            {data.msmes.map((m, i) => (
              <div className="card" key={m.msme_id}>
                <div className="flex justify-between items-start">
                  <div>
                    <div className="fw-700" style={{ fontSize: 15 }}>
                      {m.business_name}
                    </div>
                    <div className="text-sm text-muted">
                      {m.msme_id} &middot; {m.sector} &middot; {m.city}
                    </div>
                  </div>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 3,
                      background: OVERLAY_COLORS[i % OVERLAY_COLORS.length],
                      marginTop: 4,
                    }}
                  />
                </div>
                <div className="flex items-center gap-12 mt-16">
                  <div style={{ fontSize: 28, fontWeight: 800 }}>{m.overall_score}</div>
                  <RiskBadge category={m.risk_category} />
                </div>
                <div className="text-sm text-muted mt-8">
                  Confidence: {m.confidence_level} &middot; {m.data_completeness_score}% data
                </div>
                <div className="mt-16 text-sm">
                  <div className="fw-700" style={{ marginBottom: 4 }}>
                    {m.credit_recommendation.recommendation_text}
                  </div>
                  <div className="text-muted">
                    {formatINR(m.credit_recommendation.suggested_loan_amount)} @{" "}
                    {m.credit_recommendation.suggested_interest_rate_pct}%
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="card mt-24">
            <div className="card-title">Overlay Radar Comparison</div>
            <HealthRadarChart
              series={data.msmes.map((m, i) => ({
                name: m.msme_id,
                color: OVERLAY_COLORS[i % OVERLAY_COLORS.length],
                dimensions: m.dimensions,
                fillOpacity: 0.14,
              }))}
              height={420}
            />
          </div>

          <div className="card mt-24">
            <div className="card-title">Comparison Table</div>
            <table className="table">
              <thead>
                <tr>
                  <th>Metric</th>
                  {data.msmes.map((m) => (
                    <th key={m.msme_id}>{m.msme_id}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="fw-700">Overall Score</td>
                  {data.msmes.map((m) => (
                    <td key={m.msme_id}>{m.overall_score}</td>
                  ))}
                </tr>
                <tr>
                  <td className="fw-700">Risk Category</td>
                  {data.msmes.map((m) => (
                    <td key={m.msme_id}>
                      <RiskBadge category={m.risk_category} />
                    </td>
                  ))}
                </tr>
                {data.comparison_table.map((row) => (
                  <tr key={row.metric}>
                    <td>{row.metric}</td>
                    {data.msmes.map((m) => (
                      <td key={m.msme_id}>{row[m.msme_id] ?? "N/A"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
