import { RISK_COLORS } from "../utils/constants";

export function RiskBadge({ category }) {
  return <span className={`badge badge-${category}`}>{category}</span>;
}

export function LoadingSpinner({ label = "Loading..." }) {
  return (
    <div className="loading-wrap">
      <span className="spinner" />
      {label}
    </div>
  );
}

export function ErrorBox({ message }) {
  return <div className="error-box">⚠ {message}</div>;
}

export function ConfidenceBar({ level, completeness }) {
  const color = level === "High" ? "#14b8a6" : level === "Medium" ? "#f59e0b" : "#ef4444";
  return (
    <div>
      <div className="flex justify-between text-sm text-muted mt-8" style={{ marginBottom: 4 }}>
        <span>
          Confidence: <b style={{ color }}>{level}</b>
        </span>
        <span>{completeness}% data completeness</span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${completeness}%`, background: color }} />
      </div>
    </div>
  );
}

export function DataSourceChecklist({ sources }) {
  const LABELS = {
    gst: "GST (GSTR-3B)",
    upi: "UPI Transactions",
    epfo: "EPFO Payroll",
    account_aggregator: "Account Aggregator / Banking",
    utility: "Utility (Electricity/Water)",
  };
  return (
    <div className="grid grid-2" style={{ gap: 10 }}>
      {Object.entries(sources || {}).map(([key, present]) => (
        <div
          key={key}
          className="flex items-center gap-8"
          style={{
            padding: "9px 12px",
            borderRadius: 9,
            background: present ? "rgba(20,184,166,0.08)" : "rgba(239,68,68,0.06)",
            border: `1px solid ${present ? "rgba(20,184,166,0.25)" : "rgba(239,68,68,0.2)"}`,
            fontSize: 13,
          }}
        >
          <span style={{ color: present ? "#2dd4bf" : "#f87171", fontWeight: 700 }}>
            {present ? "✓" : "✗"}
          </span>
          <span style={{ color: present ? "var(--text-primary)" : "var(--text-dim)" }}>
            {LABELS[key] || key}
          </span>
        </div>
      ))}
    </div>
  );
}

export function riskColor(category) {
  return RISK_COLORS[category] || "#8b98ac";
}
