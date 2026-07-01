import { useState, useEffect } from "react";
import { getStatus, startBroadcast, stopBroadcast } from "../lib/api";
import type { BroadcastStatus as BroadcastStatusType } from "../lib/api";
import { PlatformCard } from "./PlatformCard";

export function BroadcastStatus() {
  const [status, setStatus] = useState<BroadcastStatusType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [confirmingStop, setConfirmingStop] = useState(false);

  const fetchStatus = async () => {
    try {
      const s = await getStatus();
      setStatus(s);
      setError(null);
    } catch (err) {
      setError("Failed to connect to broadcast service");
    } finally {
      setInitialLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async () => {
    if (!status) return;
    if (status.active) {
      // Show confirmation before stopping
      setConfirmingStop(true);
      return;
    }
    // Going live — immediate action
    setLoading(true);
    try {
      const s = await startBroadcast();
      setStatus(s);
    } catch {
      setError("Failed to start broadcast");
    }
    setLoading(false);
  };

  const confirmStop = async () => {
    if (!status) return;
    setLoading(true);
    setConfirmingStop(false);
    try {
      const s = await stopBroadcast();
      setStatus(s);
    } catch {
      setError("Failed to stop broadcast");
    }
    setLoading(false);
  };

  const cancelStop = () => {
    setConfirmingStop(false);
  };

  const formatUptime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) {
      return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // Error state — no data at all
  if (!status && error) {
    return (
      <div className="bg-danger-bg border border-danger/30 rounded-lg p-6 animate-fade-in" role="alert">
        <div className="flex items-start gap-3">
          <span className="text-danger text-lg leading-none mt-0.5 font-bold" aria-hidden="true">!</span>
          <div className="flex-1 min-w-0">
            <p className="text-danger font-semibold text-sm">Connection Error</p>
            <p className="text-text-secondary text-xs mt-1">{error}</p>
            <button
              onClick={fetchStatus}
              className="btn btn-ghost btn--sm mt-3 text-danger border-danger/30 hover:bg-danger/10"
            >
              Retry Connection
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Initial loading state
  if (initialLoading) {
    return (
      <div className="card flex items-center justify-center min-h-[160px]" aria-label="Loading broadcast status">
        <div className="flex items-center gap-3" role="status">
          <div className="w-5 h-5 border-2 border-brand border-t-transparent rounded-full animate-spin-slow" aria-hidden="true" />
          <span className="text-text-secondary text-sm">Connecting to broadcast service...</span>
        </div>
      </div>
    );
  }

  const platforms = status ? Object.entries(status.platforms) : [];
  const livePlatforms = platforms.filter(([, ps]) => ps.streaming);
  const hasIssues = platforms.some(([, ps]) => ps.error);

  return (
    <div className="space-y-5" aria-live="polite">
      {/* Header */}
      <div className="section-header">
        <div className="flex items-center gap-4">
          <div>
            <h2 className="section-header__title">Broadcast Control</h2>
            {status && (
              <p className="section-header__subtitle mt-0.5">
                {status.active ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span className="live-dot" />
                    <span className="font-semibold text-live">LIVE</span>
                    <span className="text-text-muted mx-1">&middot;</span>
                    <span className="data-value font-semibold text-live">
                      {formatUptime(status.uptime_seconds)}
                    </span>
                    {livePlatforms.length > 0 && (
                      <>
                        <span className="text-text-muted mx-1">&middot;</span>
                        <span className="text-text-secondary text-xs">
                          {livePlatforms.length}/{platforms.length} platforms
                        </span>
                      </>
                    )}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5">
                    <span className="live-dot live-dot--off" />
                    <span className="text-text-muted">Offline</span>
                  </span>
                )}
              </p>
            )}
          </div>
          {hasIssues && status?.active && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-warning/10 border border-warning/30">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-warning animate-pulse" />
              <span className="text-xs font-medium text-warning">Issues detected</span>
            </div>
          )}
        </div>
        <div className="section-header__actions">
          <button
            onClick={handleToggle}
            disabled={loading || confirmingStop}
            className={`btn btn--lg ${
              status?.active
                ? "btn-ghost border-danger text-danger hover:bg-danger/10 hover:border-danger"
                : "bg-live text-bg-base border-live hover:bg-live/80 active:bg-live/60"
            }`}
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                <span>{status?.active ? "Ending..." : "Starting..."}</span>
              </>
            ) : status?.active ? (
              "End Broadcast"
            ) : (
              "Go Live"
            )}
          </button>
        </div>
      </div>

      {/* Confirmation dialog for End Broadcast */}
      {confirmingStop && (
        <div className="bg-accent-bg border border-warning/40 rounded-lg p-5 animate-fade-in-down" role="alertdialog" aria-label="Confirm end broadcast">
          <div className="flex items-start gap-3">
            <span className="text-warning text-lg leading-none mt-0.5 font-bold" aria-hidden="true">!</span>
            <div className="flex-1">
              <p className="text-warning font-semibold text-sm">End Broadcast?</p>
              <p className="text-text-secondary text-xs mt-1">
                This will stop the stream on all platforms.
                {status && status.uptime_seconds > 60 && (
                  <span className="block mt-0.5">
                    Current uptime: <span className="font-mono text-warning">{formatUptime(status.uptime_seconds)}</span>
                  </span>
                )}
              </p>
              <div className="flex items-center gap-2 mt-4">
                <button
                  onClick={confirmStop}
                  disabled={loading}
                  className="btn btn-danger btn--sm"
                >
                  {loading ? "Ending..." : "Yes, End Broadcast"}
                </button>
                <button
                  onClick={cancelStop}
                  disabled={loading}
                  className="btn btn-ghost btn--sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Transient error banner — stale data still shown */}
      {error && status && (
        <div className="bg-danger-bg border border-danger/30 rounded-lg px-4 py-3 flex items-start gap-2 animate-fade-in-down" role="alert">
          <span className="text-danger text-xs leading-none mt-0.5 font-bold" aria-hidden="true">!</span>
          <p className="text-danger text-xs font-medium">{error}</p>
          <button
            onClick={fetchStatus}
            className="ml-auto text-xs text-danger underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Platform cards */}
      {status && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {platforms.map(([name, ps]) => (
            <PlatformCard key={name} name={name} status={ps} />
          ))}
        </div>
      )}
    </div>
  );
}
