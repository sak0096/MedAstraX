import { useState } from "react";
import { executeQuery, interpretQuery, rejectQuery, reviseQuery } from "../api/client";
import { trackEvent } from "../instrumentation/logger";
import type { BeneficiaryRow, ExperimentalCondition, InterpretedQuery, QueryResult } from "../types";

interface QueryPanelProps {
  onResults: (rows: BeneficiaryRow[], result: QueryResult) => void;
  condition?: ExperimentalCondition;
}

export function QueryPanel({ onResults, condition }: QueryPanelProps) {
  const [queryText, setQueryText] = useState("");
  const [interpreted, setInterpreted] = useState<InterpretedQuery | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [correctionYear, setCorrectionYear] = useState("");
  const [correctionCondition, setCorrectionCondition] = useState("");
  const [correctionClaims, setCorrectionClaims] = useState("");

  const handleInterpret = async () => {
    if (queryText.trim().length < 3) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await interpretQuery(queryText.trim());
      setInterpreted(response);
      setCorrectionYear(String(response.parameters.analytic_year ?? ""));
      setCorrectionCondition(String(response.parameters.chronic_filter ?? ""));
      setCorrectionClaims(String(response.parameters.min_total_claims ?? ""));
      void trackEvent(
        "query_submit",
        { query: queryText.trim(), query_id: response.query_id, action: response.action },
        condition,
      );
    } catch (interpretError) {
      setError(
        interpretError instanceof Error ? interpretError.message : "Failed to interpret query.",
      );
      setInterpreted(null);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!interpreted) return;
    setLoading(true);
    setError(null);
    try {
      const response = await executeQuery(interpreted.query_id);
      setResult(response);
      void trackEvent(
        "query_confirm",
        {
          query_id: interpreted.query_id,
          row_count: response.row_count,
          cached: response.cached,
        },
        condition,
      );
      onResults(response.rows, response);
    } catch (executeError) {
      setError(
        executeError instanceof Error ? executeError.message : "Failed to execute query.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!interpreted) return;
    setLoading(true);
    setError(null);
    try {
      await rejectQuery(interpreted.query_id);
      void trackEvent("query_reject", { query_id: interpreted.query_id, action: interpreted.action }, condition);
      setInterpreted(null);
      setResult(null);
    } catch (rejectError) {
      setError(rejectError instanceof Error ? rejectError.message : "Failed to cancel the interpretation.");
    } finally {
      setLoading(false);
    }
  };

  const handleRevise = async () => {
    if (!interpreted) return;
    setLoading(true);
    setError(null);
    try {
      const corrections: {
        analytic_year?: number;
        chronic_filter?: string;
        min_total_claims?: number;
      } = {};
      if (correctionYear.trim()) corrections.analytic_year = Number(correctionYear);
      if (correctionCondition.trim()) corrections.chronic_filter = correctionCondition.trim();
      if (correctionClaims.trim()) corrections.min_total_claims = Number(correctionClaims);
      const revised = await reviseQuery(interpreted.query_id, corrections);
      setInterpreted(revised);
      setResult(null);
      void trackEvent("query_revise", { query_id: interpreted.query_id, revised_query_id: revised.query_id }, condition);
    } catch (reviseError) {
      setError(reviseError instanceof Error ? reviseError.message : "Failed to correct the interpretation.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel llm-panel">
      <div className="panel-header">
        <div>
          <h2>Ask a question</h2>
          <p className="panel-subtitle">
            The system will show how it interpreted your request. Confirm before it runs.
          </p>
        </div>
      </div>

      <div className="query-input-row">
        <input
          type="text"
          className="query-input"
          placeholder='e.g. "top 10 hospitalization risk with diabetes"'
          value={queryText}
          onChange={(event) => setQueryText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void handleInterpret();
          }}
        />
        <button type="button" className="secondary-button" onClick={() => void handleInterpret()} disabled={loading}>
          Interpret
        </button>
      </div>

      {error ? <p className="query-error">{error}</p> : null}

      {interpreted ? (
        <div className="interpretation-card">
          <h3>Confirm before running</h3>
          <p>{interpreted.confirmation_message}</p>
          <pre className="interpretation-json">{JSON.stringify(interpreted.parameters, null, 2)}</pre>
          <div className="study-response-field">
            <span>Correct the interpretation before running</span>
            <label>
              Analytic year
              <input value={correctionYear} onChange={(event) => setCorrectionYear(event.target.value)} />
            </label>
            <label>
              Condition filter
              <select value={correctionCondition} onChange={(event) => setCorrectionCondition(event.target.value)}>
                <option value="">Unchanged</option>
                <option value="has_diabetes">has_diabetes</option>
                <option value="has_chf">has_chf</option>
                <option value="has_copd">has_copd</option>
                <option value="has_ckd">has_ckd</option>
                <option value="has_hypertension">has_hypertension</option>
              </select>
            </label>
            <label>
              Minimum claims
              <input value={correctionClaims} onChange={(event) => setCorrectionClaims(event.target.value)} />
            </label>
          </div>
          <div className="query-actions">
            <button type="button" className="secondary-button" onClick={() => void handleConfirm()} disabled={loading}>
              Confirm &amp; run
            </button>
            <button type="button" className="ghost-button" onClick={() => void handleRevise()} disabled={loading}>
              Correct interpretation
            </button>
            <button type="button" className="ghost-button" onClick={() => void handleReject()} disabled={loading}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="query-result-card">
          <h3>Result</h3>
          {result.row_count === 0 ? <p>No matching records.</p> : null}
          {result.grounded_narrative ? <p>{result.grounded_narrative}</p> : null}
          {result.fallback ? (
            <p className="fallback-banner">Insufficient evidence for a grounded narrative.</p>
          ) : null}
          <p className="result-meta">
            {result.row_count.toLocaleString()} rows · {result.cached ? "cached" : "fresh"} execution
          </p>
          {result.claims.length > 0 ? (
            <ul className="evidence-claim-list compact">
              {result.claims.map((claim, index) => (
                <li key={`${claim.statement}-${index}`}>
                  <span>{claim.statement}</span>
                  <span className="evidence-links inline">
                    {claim.source_fields.join(", ")}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
