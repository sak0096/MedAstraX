import { useEffect, useState } from "react";
import { exportStudySession } from "../api/client";
import { getSessionId } from "../instrumentation/logger";

interface StudyExportButtonProps {
  enabled: boolean;
}

export function StudyExportButton({ enabled }: StudyExportButtonProps) {
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    const persist = () => {
      void exportStudySession(getSessionId())
        .then((response) => {
          setStatus(`Session saved (${response.event_count} events).`);
        })
        .catch(() => {
          /* autosave must not interrupt the session */
        });
    };
    persist();
    const timer = window.setInterval(persist, 30000);
    window.addEventListener("pagehide", persist);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("pagehide", persist);
      persist();
    };
  }, [enabled]);

  if (!enabled) return null;

  const handleExport = async () => {
    setLoading(true);
    try {
      const response = await exportStudySession(getSessionId());
      setStatus(`Downloaded snapshot with ${response.event_count} events.`);
    } catch (exportError) {
      setStatus(exportError instanceof Error ? exportError.message : "Failed to export session.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="study-export">
      <span className="study-export-status">{status ?? "Events save automatically."}</span>
      <button type="button" className="ghost-button" onClick={() => void handleExport()} disabled={loading}>
        Download session snapshot
      </button>
    </div>
  );
}
