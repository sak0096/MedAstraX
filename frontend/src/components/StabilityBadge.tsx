import type { StabilityBadge as StabilityBadgeType } from "../types";

interface StabilityBadgeProps {
  badge: StabilityBadgeType;
  score?: number | null;
  compact?: boolean;
}

const LABELS: Record<StabilityBadgeType, string> = {
  green: "Stable",
  yellow: "Mixed",
  red: "Unstable",
};

export function StabilityBadge({ badge, score, compact = false }: StabilityBadgeProps) {
  return (
    <span
      className={`stability-badge ${badge}`}
      title={
        score !== undefined && score !== null
          ? `Top-feature agreement under background resampling: ${score.toFixed(2)}`
          : "Bootstrap top-feature agreement (study cases) or dominance margin (bulk)"
      }
    >
      {compact ? badge[0].toUpperCase() + badge.slice(1) : LABELS[badge]}
    </span>
  );
}
