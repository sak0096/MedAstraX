import type { StabilityBadge as StabilityBadgeType } from "../types";

interface StabilityBadgeProps {
  badge: StabilityBadgeType;
  score?: number | null;
  compact?: boolean;
}

const LABELS: Record<StabilityBadgeType, string> = {
  green: "Dominant",
  yellow: "Mixed",
  red: "Diffuse",
};

export function StabilityBadge({ badge, score, compact = false }: StabilityBadgeProps) {
  return (
    <span
      className={`stability-badge ${badge}`}
      title={
        score !== undefined && score !== null
          ? `Top-feature dominance score: ${score.toFixed(2)} (not perturbation stability)`
          : "Top-feature dominance (gap between leading contributions)"
      }
    >
      {compact ? badge[0].toUpperCase() + badge.slice(1) : LABELS[badge]}
    </span>
  );
}
