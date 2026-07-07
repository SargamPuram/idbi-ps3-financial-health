import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { endpoints } from "../api/client";
import StatCard from "../components/StatCard";
import { LoadingSpinner, ErrorBox } from "../components/Misc";
import { DIMENSION_COLORS, DIMENSION_LABELS } from "../utils/constants";

const chartTooltip = {
  contentStyle: { background: "#1a2332", border: "1px solid #28374f", borderRadius: 10, fontSize: 12.5 },
};

const BUCKET_COLORS = { "0-200": "#ef4444", "200-400": "#ef4444", "400-600": "#f59e0b", "600-800": "#3b82f6", "800-1000": "#14b8a6" };

export default function Analytics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    endpoints
      .analytics()
      .then((res) => setData(res.data))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <LoadingSpinner label="Loading analytics..." />;

  const histData = Object.entries(data.score_distribution_histogram).map(([bucket, count]) => ({ bucket, count }));
  const sectorApproval = Object.entries(data.sector_approval_rates_pct).map(([sector, pct]) => ({ sector, pct }));
  const completeness = Object.entries(data.data_completeness_by_source_pct).map(([source, pct]) => ({
    source: source.toUpperCase(),
    present: pct,
    missing: Math.round((100 - pct) * 10) / 10,
  }));
  const dimAverages = Object.entries(data.average_scores_by_dimension).map(([dim, score]) => ({
    dimension: DIMENSION_LABELS[dim],
    score,
    color: DIMENSION_COLORS[dim],
  }));

  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">Portfolio Intelligence</div>
        <h1>Analytics</h1>
        <p>Score distribution, sector approval rates, data-completeness gaps and thin-file analysis across the portfolio.</p>
      </div>

      <div className="grid grid-3">
        <StatCard label="Thin-File MSMEs" value={data.thin_file_analysis.thin_file_count} accent="#ef4444" sub={`${data.thin_file_analysis.thin_file_pct}% of portfolio (<3 data sources)`} />
        <StatCard label="High Confidence Assessments" value={data.confidence_level_breakdown.High || 0} accent="#14b8a6" />
        <StatCard label="Medium/Low Confidence" value={(data.confidence_level_breakdown.Medium || 0) + (data.confidence_level_breakdown.Low || 0)} accent="#f59e0b" />
      </div>

      <div className="grid grid-2 mt-24">
        <div className="card">
          <div className="card-title">Score Distribution Histogram</div>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={histData} margin={{ left: -20 }}>
              <CartesianGrid stroke="#28374f" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="bucket" tick={{ fill: "#8b98ac", fontSize: 11 }} />
              <YAxis tick={{ fill: "#8b98ac", fontSize: 11 }} />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {histData.map((d) => (
                  <Cell key={d.bucket} fill={BUCKET_COLORS[d.bucket]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-title">Sector-wise Approval Rates</div>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={sectorApproval} margin={{ left: -20 }}>
              <CartesianGrid stroke="#28374f" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="sector" tick={{ fill: "#8b98ac", fontSize: 11 }} />
              <YAxis tick={{ fill: "#8b98ac", fontSize: 11 }} unit="%" />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="pct" fill="#3b82f6" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-2 mt-24">
        <div className="card">
          <div className="card-title">Data Completeness by Source</div>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={completeness} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid stroke="#28374f" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#8b98ac", fontSize: 11 }} unit="%" />
              <YAxis type="category" dataKey="source" tick={{ fill: "#8b98ac", fontSize: 11 }} width={80} />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="present" fill="#14b8a6" radius={[0, 6, 6, 0]} name="% present" />
            </BarChart>
          </ResponsiveContainer>
          <div className="text-sm text-dim mt-8">{data.thin_file_analysis.definition}</div>
        </div>

        <div className="card">
          <div className="card-title">Average Score by Dimension</div>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={dimAverages} margin={{ left: -20 }}>
              <CartesianGrid stroke="#28374f" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="dimension" tick={{ fill: "#8b98ac", fontSize: 10 }} />
              <YAxis tick={{ fill: "#8b98ac", fontSize: 11 }} domain={[0, 200]} />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                {dimAverages.map((d) => (
                  <Cell key={d.dimension} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card mt-24">
        <div className="card-title">Monthly Assessment Volume Trend</div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data.monthly_assessment_volume} margin={{ left: -20 }}>
            <CartesianGrid stroke="#28374f" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: "#8b98ac", fontSize: 11 }} />
            <YAxis tick={{ fill: "#8b98ac", fontSize: 11 }} />
            <Tooltip {...chartTooltip} />
            <Line type="monotone" dataKey="count" stroke="#14b8a6" strokeWidth={2.5} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
