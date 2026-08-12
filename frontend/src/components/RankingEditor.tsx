interface RankingEditorProps {
  caseIds: string[];
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}

export function RankingEditor({ caseIds, value, onChange, disabled }: RankingEditorProps) {
  const ordered = value.length === caseIds.length ? value : caseIds;

  const move = (index: number, direction: -1 | 1) => {
    const next = [...ordered];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    const current = next[index];
    next[index] = next[target];
    next[target] = current;
    onChange(next);
  };

  return (
    <ol className="ranking-editor">
      {ordered.map((caseId, index) => (
        <li key={caseId} className="ranking-row">
          <span className="ranking-index">{index + 1}</span>
          <strong>{caseId}</strong>
          <span className="ranking-actions">
            <button type="button" className="ghost-button" disabled={disabled || index === 0} onClick={() => move(index, -1)}>
              Up
            </button>
            <button
              type="button"
              className="ghost-button"
              disabled={disabled || index === ordered.length - 1}
              onClick={() => move(index, 1)}
            >
              Down
            </button>
          </span>
        </li>
      ))}
    </ol>
  );
}
