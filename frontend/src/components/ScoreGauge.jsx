import { useAnimatedCounter } from "../hooks/useAnimatedCounter";
import { riskColor } from "./Misc";

export default function ScoreGauge({ score, riskCategory, size = 220 }) {
  const animated = useAnimatedCounter(score, 1200);
  const color = riskColor(riskCategory);
  const radius = size / 2 - 14;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(1, animated / 1000));
  const offset = circumference * (1 - pct);
  const center = size / 2;

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={14}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={14}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke 0.3s ease", filter: `drop-shadow(0 0 8px ${color}66)` }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{ fontSize: size * 0.19, fontWeight: 800, letterSpacing: "-0.02em" }}>
          {Math.round(animated)}
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>out of 1000</div>
      </div>
    </div>
  );
}
