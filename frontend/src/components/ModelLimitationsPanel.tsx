interface ModelLimitationsPanelProps {
  priorityRuleDescription?: string;
}

export function ModelLimitationsPanel({ priorityRuleDescription }: ModelLimitationsPanelProps) {
  return (
    <section className="panel study-limitations">
      <h2>Data and model information</h2>
      <ul className="limitations-list">
        <li>Beneficiary records are synthetic research data — not real patients.</li>
        <li>Risk scores are model estimates for operational review, not diagnoses.</li>
        <li>Some system outputs may be inaccurate, incomplete, or inconsistent. Verify against the record when it matters.</li>
        <li>Administrative claims do not capture full clinical context or social determinants.</li>
      </ul>
      {priorityRuleDescription ? (
        <div className="priority-rule-box">
          <h3>Operational outreach priority rule</h3>
          <p>{priorityRuleDescription}</p>
        </div>
      ) : null}
    </section>
  );
}
