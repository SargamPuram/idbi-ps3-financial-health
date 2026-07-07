import { useEffect, useMemo, useState } from "react";
import { endpoints } from "../api/client";
import HealthRadarChart from "../components/HealthRadarChart";
import ScoreGauge from "../components/ScoreGauge";
import { LoadingSpinner, ErrorBox, RiskBadge } from "../components/Misc";
import { DIMENSION_LABELS } from "../utils/constants";

function Slider({ label, value, onChange, min, max, step = 1, unit = "%" }) {
  return (
    <div className="mt-16">
      <div className="flex justify-between text-sm" style={{ marginBottom: 6 }}>
        <span className="text-muted">{label}</span>
        <span className="fw-700" style={{ color: "#14b8a6" }}>
          {value > 0 ? "+" : ""}
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: "100%", accentColor: "#14b8a6" }}
      />
    </div>
  );
}

export default function Simulator() {
  const [msmeId, setMsmeId] = useState("MSME00001");
  const [recentIds, setRecentIds] = useState([]);
  const [gstIncrease, setGstIncrease] = useState(0);
  const [bouncesTarget, setBouncesTarget] = useState(null);
  const [empGrowth, setEmpGrowth] = useState(0);
  const [upiIncrease, setUpiIncrease] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    endpoints.portfolio().then((res) => {
      setRecentIds(res.data.recent_assessments.map((r) => r.msme_id));
    });
  }, []);

  const payload = useMemo(
    () => ({
      msme_id: msmeId,
      gst_turnover_increase_pct: gstIncrease,
      cheque_bounces_target: bouncesTarget,
      employee_growth_increase_pct: empGrowth,
      upi_volume_increase_pct: upiIncrease,
    }),
    [msmeId, gstIncrease, bouncesTarget, empGrowth, upiIncrease]
  );

  useEffect(() => {
    if (!msmeId) return;
    setLoading(true);
    setError(null);
    const handle = setTimeout(() => {
      endpoints
        .simulate(payload)
        .then((res) => setResult(res.data))
        .catch((e) => setError(e.response?.status === 404 ? `MSME '${msmeId}' not found` : e.message))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payload]);

  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">What-If Analysis</div>
        <h1>Financial Health Simulator</h1>
        <p>Adjust alternate-data signals and see the projected impact on an MSME's health score in real time.</p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "320px 1fr", gap: 20 }}>
        <div className="card">
          <div className="card-title">Select MSME</div>
          <input
            className="input"
            list="recent-msmes"
            value={msmeId}
            onChange={(e) => setMsmeId(e.target.value.trim())}
            placeholder="e.g. MSME00001"
            style={{ width: "100%" }}
          />
          <datalist id="recent-msmes">
            {recentIds.map((id) => (
              <option key={id} value={id} />
            ))}
          </datalist>
          <div className="text-sm text-dim mt-8">Type any ID from MSME00001 to MSME05000, or pick a recent one.</div>

          <div className="mt-24">
            <Slider label="GST turnover increases by" value={gstIncrease} onChange={setGstIncrease} min={-30} max={60} />
            <Slider
              label="Cheque bounces reduce to"
              value={bouncesTarget ?? 0}
              onChange={setBouncesTarget}
              min={0}
              max={6}
              unit=" /yr"
            />
            <Slider label="Employee count grows by" value={empGrowth} onChange={setEmpGrowth} min={-30} max={60} />
            <Slider label="UPI transaction volume increases by" value={upiIncrease} onChange={setUpiIncrease} min={-30} max={60} />
          </div>
          <button
            className="btn btn-secondary mt-16"
            style={{ width: "100%" }}
            onClick={() => {
              setGstIncrease(0);
              setBouncesTarget(null);
              setEmpGrowth(0);
              setUpiIncrease(0);
            }}
          >
            Reset Sliders
          </button>
        </div>

        <div>
          {error && <ErrorBox message={error} />}
          {!error && !result && <LoadingSpinner label="Simulating..." />}
          {result && (
            <>
              <div className="grid grid-2">
                <div className="card flex flex-col items-center">
                  <div className="card-title" style={{ width: "100%" }}>
                    Current Score
                  </div>
                  <ScoreGauge score={result.current_score} riskCategory={result.current_risk_category} size={170} />
                  <div style={{ marginTop: 10 }}>
                    <RiskBadge category={result.current_risk_category} />
                  </div>
                </div>
                <div className="card flex flex-col items-center">
                  <div className="card-title" style={{ width: "100%" }}>
                    Projected Score{" "}
                    {loading && <span className="spinner" style={{ marginLeft: 8 }} />}
                  </div>
                  <ScoreGauge score={result.projected_score} riskCategory={result.projected_risk_category} size={170} />
                  <div style={{ marginTop: 10 }}>
                    <RiskBadge category={result.projected_risk_category} />
                  </div>
                  <div
                    className="fw-700 mt-8"
                    style={{ color: result.score_delta >= 0 ? "#2dd4bf" : "#f87171" }}
                  >
                    {result.score_delta >= 0 ? "▲" : "▼"} {Math.abs(result.score_delta)} points
                  </div>
                </div>
              </div>

              <div className="card mt-16">
                <div className="card-title">Current vs Projected — Radar Overlay</div>
                <HealthRadarChart
                  series={[
                    { name: "Current", color: "#5f6b80", dimensions: result.current_scoring.dimensions, fillOpacity: 0.12 },
                    { name: "Projected", color: "#14b8a6", dimensions: result.projected_scoring.dimensions, fillOpacity: 0.28 },
                  ]}
                />
              </div>

              <div className="card mt-16">
                <div className="card-title">Impact Breakdown by Dimension</div>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Dimension</th>
                      <th>Baseline</th>
                      <th>Projected</th>
                      <th>Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.dimension_deltas).map(([key, d]) => (
                      <tr key={key} style={{ cursor: "default" }}>
                        <td className="fw-700">{DIMENSION_LABELS[key]}</td>
                        <td>{d.baseline ?? "N/A"}</td>
                        <td>{d.projected ?? "N/A"}</td>
                        <td style={{ color: d.delta > 0 ? "#2dd4bf" : d.delta < 0 ? "#f87171" : "var(--text-muted)" }}>
                          {d.delta != null ? `${d.delta > 0 ? "+" : ""}${d.delta}` : "N/A"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
