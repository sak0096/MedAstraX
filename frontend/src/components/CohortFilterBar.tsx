import { FEATURE_LABELS } from "../utils/xai";

export interface CohortFilterState {
  chronicFilter: string | null;
  minTotalClaims: number | null;
}

interface CohortFilterBarProps {
  filters: CohortFilterState;
  onChange: (filters: CohortFilterState) => void;
}

const CHRONIC_OPTIONS = [
  ["has_diabetes", "Diabetes"],
  ["has_chf", "Heart failure"],
  ["has_copd", "COPD"],
  ["has_ckd", "Chronic kidney disease"],
  ["has_hypertension", "Hypertension"],
] as const;

export function CohortFilterBar({ filters, onChange }: CohortFilterBarProps) {
  const chips: Array<{ key: string; label: string }> = [];
  if (filters.chronicFilter) {
    chips.push({
      key: "chronic",
      label: FEATURE_LABELS[filters.chronicFilter] ?? filters.chronicFilter,
    });
  }
  if (filters.minTotalClaims !== null) {
    chips.push({
      key: "claims",
      label: `At least ${filters.minTotalClaims} claims`,
    });
  }

  return (
    <section className="panel filter-panel">
      <div className="panel-header">
        <div>
          <h2>Cohort filters</h2>
          <p className="panel-subtitle">Active filters stay visible so you can check what the table includes.</p>
        </div>
      </div>
      <div className="filter-controls">
        <label className="study-response-field">
          <span>Chronic condition</span>
          <select
            value={filters.chronicFilter ?? ""}
            onChange={(event) =>
              onChange({
                ...filters,
                chronicFilter: event.target.value || null,
              })
            }
          >
            <option value="">Any</option>
            {CHRONIC_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="study-response-field">
          <span>Minimum total claims</span>
          <input
            type="number"
            min={0}
            placeholder="None"
            value={filters.minTotalClaims ?? ""}
            onChange={(event) =>
              onChange({
                ...filters,
                minTotalClaims: event.target.value === "" ? null : Number(event.target.value),
              })
            }
          />
        </label>
        <button
          type="button"
          className="ghost-button"
          onClick={() => onChange({ chronicFilter: null, minTotalClaims: null })}
        >
          Clear filters
        </button>
      </div>
      <div className="filter-chips" aria-label="Active filters">
        {chips.length === 0 ? (
          <span className="muted">No filters applied</span>
        ) : (
          chips.map((chip) => (
            <span key={chip.key} className="filter-chip">
              {chip.label}
            </span>
          ))
        )}
      </div>
    </section>
  );
}
