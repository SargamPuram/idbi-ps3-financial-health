export function formatINR(value, { compact = true } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const num = Number(value);
  if (compact) {
    if (Math.abs(num) >= 1e7) return `₹${(num / 1e7).toFixed(2)} Cr`;
    if (Math.abs(num) >= 1e5) return `₹${(num / 1e5).toFixed(2)} L`;
    if (Math.abs(num) >= 1e3) return `₹${(num / 1e3).toFixed(1)} K`;
  }
  return `₹${num.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function formatNumber(value, decimals = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatPct(value, decimals = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `${Number(value).toFixed(decimals)}%`;
}
