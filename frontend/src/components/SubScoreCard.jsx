import { useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { DIMENSION_COLORS, DIMENSION_LABELS } from "../utils/constants";

const ICONS = {
  revenue_health: "📈",
  operational_health: "⚙️",
  credit_discipline: "🛡️",
  digital_maturity: "📲",
  sector_benchmark: "🏆",
};

const STATUS_COLOR = { "On-time": "#14b8a6", Late: "#f59e0b", Missed: "#ef4444" };

function StatusHeatmap({ months, statuses }) {
  return (
    <div className="flex gap-8" style={{ flexWrap: "wrap" }}>
      {months.map((m, i) => (
        <div key={m} style={{ textAlign: "center" }}>
          <div
            title={`${m}: ${statuses[i] || "N/A"}`}
            style={{
              width: 22,
              height: 22,
              borderRadius: 5,
              background: STATUS_COLOR[statuses[i]] || "#2a3852",
              marginBottom: 4,
            }}
          />
          <div style={{ fontSize: 9, color: "var(--text-dim)" }}>{m?.slice(5)}</div>
        </div>
      ))}
    </div>
  );
}

function chartTheme() {
  return {
    grid: "#28374f",
    axis: "#5f6b80",
    tooltipStyle: {
      background: "#1a2332",
      border: "1px solid #28374f",
      borderRadius: 10,
      fontSize: 12,
    },
  };
}

function DimensionChart({ dimKey, monthlySeries, sectorComparison, color }) {
  const t = chartTheme();
  const months = (monthlySeries?.months || []).map((m) => m || "");

  if (dimKey === "revenue_health") {
    const data = months.map((m, i) => ({ month: m, turnover: monthlySeries.gst_turnover_trend?.[i] }));
    const hasData = data.some((d) => d.turnover != null);
    if (!hasData) return <NoDataNote text="No GST data available for this MSME" />;
    return (
      <>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={data} margin={{ left: -20, top: 6 }}>
            <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: t.axis, fontSize: 10 }} tickFormatter={(v) => v?.slice(5)} />
            <YAxis tick={{ fill: t.axis, fontSize: 10 }} tickFormatter={(v) => `${(v / 1e5).toFixed(1)}L`} />
            <Tooltip contentStyle={t.tooltipStyle} formatter={(v) => [`₹${Number(v).toLocaleString("en-IN")}`, "Turnover"]} />
            <Area type="monotone" dataKey="turnover" stroke={color} fill={color} fillOpacity={0.25} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
        <div className="mt-8">
          <div className="text-sm text-muted mt-8" style={{ marginBottom: 6 }}>GST filing calendar (12 months)</div>
          <StatusHeatmap months={months} statuses={monthlySeries.filing_status || []} />
        </div>
      </>
    );
  }

  if (dimKey === "operational_health") {
    const data = months.map((m, i) => ({
      month: m,
      employees: monthlySeries.employee_count_trend?.[i],
      electricity: monthlySeries.electricity_trend?.[i],
    }));
    return (
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ left: -20, top: 6 }}>
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="month" tick={{ fill: t.axis, fontSize: 10 }} tickFormatter={(v) => v?.slice(5)} />
          <YAxis yAxisId="left" tick={{ fill: t.axis, fontSize: 10 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fill: t.axis, fontSize: 10 }} />
          <Tooltip contentStyle={t.tooltipStyle} />
          <Line yAxisId="left" type="monotone" dataKey="employees" stroke={color} strokeWidth={2} dot={false} name="Employees" />
          <Line yAxisId="right" type="monotone" dataKey="electricity" stroke="#f59e0b" strokeWidth={2} dot={false} name="Electricity (kWh)" />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (dimKey === "credit_discipline") {
    const hasData = (monthlySeries.loan_repayment_status || []).some((v) => v != null);
    if (!hasData) return <NoDataNote text="No Account Aggregator / banking data available for this MSME" />;
    return (
      <div>
        <div className="text-sm text-muted" style={{ marginBottom: 6 }}>Loan repayment history (12 months)</div>
        <StatusHeatmap months={months} statuses={monthlySeries.loan_repayment_status || []} />
        <div className="mt-16">
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={months.map((m, i) => ({ month: m, bounce: monthlySeries.cheque_bounce_flag?.[i] || 0 }))} margin={{ left: -20, top: 6 }}>
              <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: t.axis, fontSize: 10 }} tickFormatter={(v) => v?.slice(5)} />
              <YAxis tick={{ fill: t.axis, fontSize: 10 }} allowDecimals={false} />
              <Tooltip contentStyle={t.tooltipStyle} />
              <Bar dataKey="bounce" fill="#ef4444" name="Cheque bounces" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if (dimKey === "digital_maturity") {
    const data = months.map((m, i) => ({
      month: m,
      volume: monthlySeries.upi_volume_trend?.[i],
      ticket: monthlySeries.avg_ticket_size_trend?.[i],
    }));
    return (
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ left: -20, top: 6 }}>
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="month" tick={{ fill: t.axis, fontSize: 10 }} tickFormatter={(v) => v?.slice(5)} />
          <YAxis yAxisId="left" tick={{ fill: t.axis, fontSize: 10 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fill: t.axis, fontSize: 10 }} />
          <Tooltip contentStyle={t.tooltipStyle} />
          <Line yAxisId="left" type="monotone" dataKey="volume" stroke={color} strokeWidth={2} dot={false} name="UPI txns/month" />
          <Line yAxisId="right" type="monotone" dataKey="ticket" stroke="#8b5cf6" strokeWidth={2} dot={false} name="Avg ticket size (₹)" />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (dimKey === "sector_benchmark") {
    const data = (sectorComparison || []).map((r) => ({
      metric: r.metric,
      "This MSME": r.this_msme,
      "Sector Median": r.sector_median,
    }));
    return (
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} layout="vertical" margin={{ left: 40, top: 6 }}>
          <CartesianGrid stroke={t.grid} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fill: t.axis, fontSize: 10 }} />
          <YAxis type="category" dataKey="metric" tick={{ fill: t.axis, fontSize: 10 }} width={130} />
          <Tooltip contentStyle={t.tooltipStyle} />
          <Bar dataKey="This MSME" fill={color} radius={[0, 3, 3, 0]} />
          <Bar dataKey="Sector Median" fill="#5f6b80" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return null;
}

function NoDataNote({ text }) {
  return (
    <div className="text-sm text-dim" style={{ padding: "16px 0", fontStyle: "italic" }}>
      {text} — weight redistributed to other available dimensions.
    </div>
  );
}

export default function SubScoreCard({ dimKey, dimData, monthlySeries, sectorComparison, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const color = DIMENSION_COLORS[dimKey];
  const available = dimData?.available;
  const pct = available ? (dimData.display_score / 200) * 100 : 0;

  return (
    <div className="accordion-item">
      <div className="accordion-header" onClick={() => setOpen((o) => !o)}>
        <div className="flex items-center gap-12">
          <span style={{ fontSize: 20 }}>{ICONS[dimKey]}</span>
          <div>
            <div className="fw-700">{DIMENSION_LABELS[dimKey]}</div>
            <div className="text-sm text-muted">Weight: {dimData?.weight_pct}% of overall score</div>
          </div>
        </div>
        <div className="flex items-center gap-16">
          {available ? (
            <div style={{ textAlign: "right", minWidth: 140 }}>
              <div className="fw-700" style={{ color }}>
                {dimData.display_score} / 200
              </div>
              <div className="bar-track" style={{ marginTop: 4 }}>
                <div className="bar-fill" style={{ width: `${pct}%`, background: color }} />
              </div>
            </div>
          ) : (
            <span className="badge badge-neutral">Not available</span>
          )}
          <span style={{ color: "var(--text-muted)", transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>
            ▾
          </span>
        </div>
      </div>
      <div className={`accordion-body${open ? " open" : ""}`}>
        <DimensionChart dimKey={dimKey} monthlySeries={monthlySeries} sectorComparison={sectorComparison} color={color} />
        {available && (
          <div className="grid grid-2 mt-16" style={{ gap: 8 }}>
            {Object.entries(dimData.components || {}).map(([key, c]) => (
              <div key={key} className="flex justify-between text-sm" style={{ padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                <span className="text-muted">{c.label}</span>
                <span className="fw-700">{c.score.toFixed(0)}/100</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
