import { useAnimatedCounter } from "../hooks/useAnimatedCounter";

export default function StatCard({ label, value, suffix = "", decimals = 0, sub, accent = "#14b8a6", format }) {
  const animated = useAnimatedCounter(typeof value === "number" ? value : 0);
  const display =
    typeof value === "number"
      ? format
        ? format(animated)
        : `${animated.toFixed(decimals)}${suffix}`
      : value;

  return (
    <div className="stat-card" style={{ "--accent": accent }}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{display}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
