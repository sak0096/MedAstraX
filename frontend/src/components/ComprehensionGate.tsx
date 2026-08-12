import { useMemo, useState } from "react";
import { submitComprehension } from "../api/client";
import { getParticipantId, getSessionId } from "../instrumentation/logger";
import {
  incrementComprehensionAttempts,
  markComprehensionPassed,
} from "../study/session";

export interface ComprehensionQuestion {
  question_id: string;
  prompt: string;
  choices: string[];
  correct_index: number;
}

interface ComprehensionGateProps {
  questions: ComprehensionQuestion[];
  passThreshold: number;
  onPassed: () => void;
  attemptKey?: string;
  maxAttempts?: number;
}

export function ComprehensionGate({
  questions,
  passThreshold,
  onPassed,
  attemptKey = "default",
  maxAttempts = 2,
}: ComprehensionGateProps) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [lockedOut, setLockedOut] = useState(false);

  const allAnswered = useMemo(
    () => questions.every((question) => answers[question.question_id] !== undefined),
    [answers, questions],
  );

  const submit = async () => {
    setError(null);
    try {
      const attempts = incrementComprehensionAttempts(attemptKey);
      const response = await submitComprehension({
        participant_id: getParticipantId(),
        session_id: getSessionId(),
        answers,
      });
      if (response.passed) {
        markComprehensionPassed(attemptKey);
        setResult(`Passed (${response.correct}/${response.total}).`);
        onPassed();
        return;
      }
      if (attempts >= maxAttempts) {
        setLockedOut(true);
        setResult(
          `Did not pass after ${maxAttempts} attempts (${response.correct}/${response.total}). Please notify the facilitator.`,
        );
        return;
      }
      setResult(`Review the instructions and try once more (${response.correct}/${response.total}).`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to submit comprehension check.");
    }
  };

  return (
    <section className="panel study-comprehension">
      <h2>Comprehension check</h2>
      <p className="panel-subtitle">
        Answer all questions before continuing. You need at least {passThreshold} correct responses.
        One retry is allowed.
      </p>
      {questions.map((question) => (
        <fieldset key={question.question_id} className="comprehension-question">
          <legend>{question.prompt}</legend>
          {question.choices.map((choice, index) => (
            <label key={choice} className="comprehension-choice">
              <input
                type="radio"
                name={`${attemptKey}-${question.question_id}`}
                checked={answers[question.question_id] === index}
                onChange={() =>
                  setAnswers((current) => ({ ...current, [question.question_id]: index }))
                }
                disabled={lockedOut}
              />
              <span>{choice}</span>
            </label>
          ))}
        </fieldset>
      ))}
      {error ? <p className="query-error">{error}</p> : null}
      {result ? <p className="study-export-status">{result}</p> : null}
      <button
        type="button"
        className="secondary-button"
        disabled={!allAnswered || lockedOut}
        onClick={() => void submit()}
      >
        Submit comprehension check
      </button>
    </section>
  );
}
