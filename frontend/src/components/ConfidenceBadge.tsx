import type { RiskConfidence } from "../types";

interface ConfidenceBadgeProps {
  level?: RiskConfidence | null;
}

export function ConfidenceBadge({ level }: ConfidenceBadgeProps) {
  if (!level || level === "normal") return null;

  const label = level === "low" ? "Low confidence" : "High confidence";
  return (
    <span className={`confidence-badge ${level}`} title={`Model ${label.toLowerCase()} for this score`}>
      {label}
    </span>
  );
}
