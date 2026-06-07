import type { StabilityBadge as StabilityBadgeType } from "../types";

interface StabilityBadgeProps {
  badge: StabilityBadgeType;
  score?: number | null;
  compact?: boolean;
}

const LABELS: Record<StabilityBadgeType, string> = {
  green: "Stable",
  yellow: "Moderate",
  red: "Unstable",
};

export function StabilityBadge({ badge, score, compact = false }: StabilityBadgeProps) {
  return (
    <span className={`stability-badge ${badge}`} title={score !== undefined && score !== null ? `Stability score: ${score.toFixed(2)}` : undefined}>
      {compact ? badge[0].toUpperCase() + badge.slice(1) : LABELS[badge]}
    </span>
  );
}
