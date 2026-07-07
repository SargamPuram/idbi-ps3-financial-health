import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  PieChart,
  Pie,
} from "recharts";
import { endpoints } from "../api/client";
import StatCard from "../components/StatCard";
import { LoadingSpinner, ErrorBox, RiskBadge } from "../components/Misc";
import { RISK_COLORS } from "../utils/constants";
import { formatPct } from "../utils/format";

const RISK_ORDER = ["Prime", "Good", "Moderate", "Caution"];
const SIZE_COLORS = { Micro: "#14b8a6", Small: "#3b82f6", Medium: "#8b5cf6" };

const chartTooltip = {
  contentStyle: { background: "#1a2332", border: "1px solid #28374f", borderRadius: 10, fontSize: 12.5 },
};

export default function PortfolioOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    endpoints
      .portfolio()
      .then((res) => setData(res.data))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={`Failed to load portfolio: ${error}`} />;
  if (!data) return <LoadingSpinner label="Loading portfolio overview..." />;

  const scoreDist = RISK_ORDER.map((k) => ({ category: k, count: data.score_distribution[k] || 0 }));
  const sectorData = Object.entries(data.sector_breakdown)
    .map(([sector, count]) => ({ sector, count }))
    .sort((a, b) => b.count - a.count);
  const sizeData = Object.entries(data.msme_size_distribution).map(([name, value]) => ({ name, value }));
  const geoData = Object.entries(data.geographic_distribution)
    .slice(0, 12)
    .map(([city, count]) => ({ city, count }));

  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">IDBI Bank &middot; MSME Credit Intelligence</div>
        <h1>IDBI MSME Health Intelligence</h1>
        <p>Financial Health Scoring Engine — alternate-data underwriting for New-to-Credit &amp; New-to-Bank MSMEs</p>
      </div>

      <div className="grid grid-4">
        <StatCard label="Total MSMEs Assessed" value={data.total_msmes_assessed} accent="#14b8a6" />
        <StatCard label="Average Health Score" value={data.average_health_score} suffix=" / 1000" decimals={0} accent="#3b82f6" />
        <StatCard label="Approval Rate" value={data.approval_rate_pct} suffix="%" decimals={1} accent="#8b5cf6" />
        <StatCard label="Data Completeness" value={data.data_completeness_pct} suffix="%" decimals={1} accent="#f59e0b" />
      </div>

      <div className="grid grid-2 mt-24">
        <div className="card">
          <div className="card-title">Score Distribution by Risk Category</div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={scoreDist} margin={{ left: -20 }}>
              <CartesianGrid stroke="#28374f" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="category" tick={{ fill: "#8b98ac", fontSize: 12 }} />
              <YAxis tick={{ fill: "#8b98ac", fontSize: 11 }} />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {scoreDist.map((d) => (
                  <Cell key={d.category} fill={RISK_COLORS[d.category]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-title">Sector Breakdown</div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={sectorData} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid stroke="#28374f" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#8b98ac", fontSize: 11 }} />
              <YAxis type="category" dataKey="sector" tick={{ fill: "#8b98ac", fontSize: 12 }} width={100} />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-2 mt-24">
        <div className="card">
          <div className="card-title">MSME Size Distribution</div>
          <div className="flex items-center" style={{ gap: 24 }}>
            <ResponsiveContainer width="60%" height={200}>
              <PieChart>
                <Pie data={sizeData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>
                  {sizeData.map((d) => (
                    <Cell key={d.name} fill={SIZE_COLORS[d.name]} />
                  ))}
                </Pie>
                <Tooltip {...chartTooltip} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-12">
              {sizeData.map((d) => (
                <div key={d.name} className="flex items-center gap-8">
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: SIZE_COLORS[d.name] }} />
                  <span className="text-sm">{d.name}</span>
                  <span className="text-sm text-muted">
                    {d.value} ({formatPct((d.value / data.total_msmes_assessed) * 100)})
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Geographic Distribution (Top Cities)</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={geoData} margin={{ left: -20 }}>
              <CartesianGrid stroke="#28374f" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="city" tick={{ fill: "#8b98ac", fontSize: 10 }} angle={-30} textAnchor="end" height={55} />
              <YAxis tick={{ fill: "#8b98ac", fontSize: 11 }} />
              <Tooltip {...chartTooltip} />
              <Bar dataKey="count" fill="#8b5cf6" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card mt-24">
        <div className="card-title">Recent Assessments</div>
        <table className="table">
          <thead>
            <tr>
              <th>MSME ID</th>
              <th>Business Name</th>
              <th>Sector</th>
              <th>City</th>
              <th>Score</th>
              <th>Risk Category</th>
              <th>Assessed On</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_assessments.map((r) => (
              <tr key={r.msme_id} onClick={() => navigate(`/health-card/${r.msme_id}`)}>
                <td className="text-muted">{r.msme_id}</td>
                <td className="fw-700">{r.business_name}</td>
                <td>{r.sector}</td>
                <td>{r.city}</td>
                <td className="fw-700">{r.overall_score}</td>
                <td>
                  <RiskBadge category={r.risk_category} />
                </td>
                <td className="text-muted">{r.assessment_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
