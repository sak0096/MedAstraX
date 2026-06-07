import { useState } from "react";
import { exportStudySession } from "../api/client";
import { getSessionId } from "../instrumentation/logger";

interface StudyExportButtonProps {
  enabled: boolean;
}

export function StudyExportButton({ enabled }: StudyExportButtonProps) {
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!enabled) return null;

  const handleExport = async () => {
    setLoading(true);
    setStatus(null);
    try {
      const response = await exportStudySession(getSessionId());
      setStatus(`Exported ${response.event_count} events for this session.`);
    } catch (exportError) {
      setStatus(
        exportError instanceof Error ? exportError.message : "Failed to export session.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="study-export">
      <button
        type="button"
        className="secondary-button"
        onClick={() => void handleExport()}
        disabled={loading}
      >
        Export study session
      </button>
      {status ? <span className="study-export-status">{status}</span> : null}
    </div>
  );
}
