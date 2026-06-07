import { ExplanationPanel } from "./ExplanationPanel";
import type {
  BeneficiaryDetail as BeneficiaryDetailType,
  BeneficiaryExplanation,
  ExperimentalCondition,
  RiskTargetShort,
} from "../types";
import { formatCurrency, formatPercent, formatSex, riskBand } from "../utils/format";

interface BeneficiaryDetailProps {
  detail: BeneficiaryDetailType | null;
  loading: boolean;
  onClose: () => void;
  condition?: ExperimentalCondition;
  explanation?: BeneficiaryExplanation | null;
  explanationLoading?: boolean;
  explanationUnavailable?: boolean;
  targets?: RiskTargetShort[];
}

export function BeneficiaryDetail({
  detail,
  loading,
  onClose,
  condition = "baseline",
  explanation = null,
  explanationLoading = false,
  explanationUnavailable = false,
  targets = ["hospitalization", "high_utilization", "elevated_cost"],
}: BeneficiaryDetailProps) {
  if (!detail && !loading) return null;

  return (
    <aside className="detail-panel">
      <div className="detail-header">
        <div>
          <p className="eyebrow">Beneficiary drill-down</p>
          <h2>{detail?.bene_id ?? "Loading…"}</h2>
          {detail ? (
            <p className="panel-subtitle">
              Analytic year {detail.analytic_year} · State {detail.demographics.state_code ?? "—"}
            </p>
          ) : null}
        </div>
        <button type="button" className="ghost-button" onClick={onClose}>
          Close
        </button>
      </div>

      {loading ? (
        <p className="detail-loading">Loading beneficiary profile…</p>
      ) : detail ? (
        <div className="detail-content">
          <section>
            <h3>Demographics</h3>
            <dl className="detail-grid">
              <div>
                <dt>Age</dt>
                <dd>{detail.demographics.age ?? "—"}</dd>
              </div>
              <div>
                <dt>Sex</dt>
                <dd>{formatSex(detail.demographics.sex)}</dd>
              </div>
              <div>
                <dt>Race code</dt>
                <dd>{detail.demographics.race ?? "—"}</dd>
              </div>
              <div>
                <dt>ESRD</dt>
                <dd>{detail.demographics.esrd_ind === "1" ? "Yes" : "No"}</dd>
              </div>
            </dl>
          </section>

          {condition === "xai" ? (
            <ExplanationPanel
              explanation={explanation}
              detail={detail}
              loading={explanationLoading}
              unavailable={explanationUnavailable}
              targets={targets}
            />
          ) : null}

          <section>
            <h3>Risk scores</h3>
            <div className="risk-score-grid">
              {Object.entries(detail.risk_scores).map(([key, value]) => (
                <article key={key} className={`risk-score-card ${riskBand(value)}`}>
                  <span>{key.replace(/_/g, " ")}</span>
                  <strong>{formatPercent(value, 0)}</strong>
                </article>
              ))}
            </div>
          </section>

          <section>
            <h3>Utilization</h3>
            <dl className="detail-grid">
              <div>
                <dt>Total claims</dt>
                <dd>{detail.utilization.total_claims ?? "—"}</dd>
              </div>
              <div>
                <dt>Inpatient claims</dt>
                <dd>{detail.utilization.inpatient_claims ?? "—"}</dd>
              </div>
              <div>
                <dt>Outpatient claims</dt>
                <dd>{detail.utilization.outpatient_claims ?? "—"}</dd>
              </div>
              <div>
                <dt>Total payment</dt>
                <dd>{formatCurrency(detail.utilization.total_payment_amt)}</dd>
              </div>
              <div>
                <dt>30-day readmissions</dt>
                <dd>{detail.utilization.readmission_30d_count ?? "—"}</dd>
              </div>
            </dl>
          </section>

          <section>
            <h3>Diagnosis profile</h3>
            <p>
              {detail.diagnosis.distinct_diagnosis_count ?? 0} distinct diagnoses ·{" "}
              {detail.diagnosis.chronic_condition_count ?? 0} chronic conditions flagged
            </p>
            <ul className="chip-list">
              {detail.diagnosis.chronic_conditions.length > 0 ? (
                detail.diagnosis.chronic_conditions.map((condition) => (
                  <li key={condition.field}>{condition.label}</li>
                ))
              ) : (
                <li className="muted">No chronic condition flags in this year.</li>
              )}
            </ul>
          </section>

          <section>
            <h3>Prescriptions</h3>
            <dl className="detail-grid">
              <div>
                <dt>Fill count</dt>
                <dd>{detail.prescriptions.rx_fill_count ?? "—"}</dd>
              </div>
              <div>
                <dt>Unique drugs</dt>
                <dd>{detail.prescriptions.rx_unique_drugs ?? "—"}</dd>
              </div>
              <div>
                <dt>Days supply</dt>
                <dd>{detail.prescriptions.rx_days_supply ?? "—"}</dd>
              </div>
            </dl>
          </section>

          {detail.history.length > 1 ? (
            <section>
              <h3>Year history</h3>
              <div className="history-table-wrap">
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>Year</th>
                      <th>Claims</th>
                      <th>Hospitalization risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.history.map((row) => (
                      <tr key={row.analytic_year}>
                        <td>{row.analytic_year}</td>
                        <td>{row.total_claims ?? "—"}</td>
                        <td>{formatPercent(row.hospitalization_risk, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}
