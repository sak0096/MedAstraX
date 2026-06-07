import { useState } from "react";
import { executeQuery, interpretQuery } from "../api/client";
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

  const handleInterpret = async () => {
    if (queryText.trim().length < 3) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await interpretQuery(queryText.trim());
      setInterpreted(response);
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
      if (response.rows.length > 0) {
        onResults(response.rows, response);
      }
    } catch (executeError) {
      setError(
        executeError instanceof Error ? executeError.message : "Failed to execute query.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setInterpreted(null);
    setResult(null);
    setError(null);
  };

  return (
    <section className="panel llm-panel">
      <div className="panel-header">
        <div>
          <h2>Natural Language Query</h2>
          <p className="panel-subtitle">
            Intent is parsed into structured parameters, shown for confirmation, then executed over
            analytic tables.
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
          <div className="query-actions">
            <button type="button" className="secondary-button" onClick={() => void handleConfirm()} disabled={loading}>
              Confirm &amp; run
            </button>
            <button type="button" className="ghost-button" onClick={handleReset}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="query-result-card">
          <h3>Grounded result</h3>
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
