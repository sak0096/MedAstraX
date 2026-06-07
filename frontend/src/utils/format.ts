export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

export function formatSex(code: string | null | undefined): string {
  if (code === "1") return "Male";
  if (code === "2") return "Female";
  return code ?? "—";
}

export function riskBand(value: number | null | undefined): "low" | "medium" | "high" | "unknown" {
  if (value === null || value === undefined) return "unknown";
  if (value >= 0.7) return "high";
  if (value >= 0.4) return "medium";
  return "low";
}
