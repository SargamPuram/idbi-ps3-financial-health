import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import { DIMENSION_LABELS } from "../utils/constants";

const SHORT_LABELS = {
  revenue_health: "Revenue",
  operational_health: "Operational",
  credit_discipline: "Credit",
  digital_maturity: "Digital",
  sector_benchmark: "Sector",
};

/**
 * series: [{ name, color, dimensions: {dimKey: {display_score, available}} }]
 */
export default function HealthRadarChart({ series, height = 380 }) {
  const dims = Object.keys(DIMENSION_LABELS);
  const data = dims.map((dim) => {
    const row = { dimension: SHORT_LABELS[dim], fullLabel: DIMENSION_LABELS[dim] };
    series.forEach((s) => {
      const d = s.dimensions?.[dim];
      row[s.name] = d && d.available ? d.display_score : 0;
    });
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="#28374f" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fill: "#c3ccdb", fontSize: 13, fontWeight: 600 }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 200]}
          tick={{ fill: "#5f6b80", fontSize: 10 }}
          tickCount={5}
        />
        {series.map((s) => (
          <Radar
            key={s.name}
            name={s.name}
            dataKey={s.name}
            stroke={s.color}
            fill={s.color}
            fillOpacity={s.fillOpacity ?? 0.28}
            strokeWidth={2.5}
            isAnimationActive
            animationDuration={900}
          />
        ))}
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12.5 }} />}
        <Tooltip
          contentStyle={{
            background: "#1a2332",
            border: "1px solid #28374f",
            borderRadius: 10,
            fontSize: 12.5,
          }}
          formatter={(value) => [`${value} / 200`, ""]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
