import { useMemo, useState } from "react";
import { submitComprehension } from "../api/client";
import { getParticipantId, getSessionId } from "../instrumentation/logger";
import { markComprehensionPassed } from "../study/session";

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
}

export function ComprehensionGate({ questions, passThreshold, onPassed }: ComprehensionGateProps) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const allAnswered = useMemo(
    () => questions.every((question) => answers[question.question_id] !== undefined),
    [answers, questions],
  );

  const submit = async () => {
    setError(null);
    try {
      const response = await submitComprehension({
        participant_id: getParticipantId(),
        session_id: getSessionId(),
        answers,
      });
      if (response.passed) {
        markComprehensionPassed();
        setResult(`Passed (${response.correct}/${response.total}).`);
        onPassed();
      } else {
        setResult(`Review the priority rule and try again (${response.correct}/${response.total}).`);
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to submit comprehension check.");
    }
  };

  return (
    <section className="panel study-comprehension">
      <h2>Comprehension check</h2>
      <p className="panel-subtitle">
        Answer all questions before continuing. You need at least {passThreshold} correct responses.
      </p>
      {questions.map((question) => (
        <fieldset key={question.question_id} className="comprehension-question">
          <legend>{question.prompt}</legend>
          {question.choices.map((choice, index) => (
            <label key={choice} className="comprehension-choice">
              <input
                type="radio"
                name={question.question_id}
                checked={answers[question.question_id] === index}
                onChange={() =>
                  setAnswers((current) => ({ ...current, [question.question_id]: index }))
                }
              />
              <span>{choice}</span>
            </label>
          ))}
        </fieldset>
      ))}
      {error ? <p className="query-error">{error}</p> : null}
      {result ? <p className="study-export-status">{result}</p> : null}
      <button type="button" className="secondary-button" disabled={!allAnswered} onClick={() => void submit()}>
        Submit comprehension check
      </button>
    </section>
  );
}
