import { useState, useEffect, useCallback } from "react";
import {
  getDashboardData,
  getSessionReport,
  getSessionReportCsv,
  getLiveMetrics,
} from "../lib/api";
import type {
  DashboardData,
  AnalyticsReport,
  LiveMetrics,
} from "../lib/api";

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatDate(ts: number): string {
  return new Date(ts * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AnalyticsPanel() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [liveMetrics, setLiveMetrics] = useState<LiveMetrics | null>(null);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [dash, live] = await Promise.all([
        getDashboardData(),
        getLiveMetrics(),
      ]);
      setDashboard(dash);
      setLiveMetrics(live);
      setError(null);
    } catch {
      setError("Failed to load analytics data");
    }
    setInitialLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleSelectSession = async (id: string) => {
    setSelectedSession(id);
    setLoading(true);
    try {
      const r = await getSessionReport(id);
      setReport(r);
      setError(null);
    } catch {
      setError("Failed to load report");
      setReport(null);
    }
    setLoading(false);
  };

  const handleDownloadCsv = async (id: string) => {
    try {
      const csv = await getSessionReportCsv(id);
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `session_${id}_metrics.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Failed to download CSV");
    }
  };

  const liveSession = liveMetrics?.live ? liveMetrics.session : null;
  const recentSessions = dashboard?.recent_sessions ?? [];
  const totals = dashboard?.totals;

  return (
    <div className="bg-surface border border-border rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text uppercase tracking-[0.08em]">Analytics</h2>
        <button
          onClick={fetchData}
          className="px-3 py-1.5 text-xs font-medium border border-border rounded-lg text-text-secondary bg-hover hover:bg-elevated hover:text-text focus:outline-none focus:ring-2 focus:ring-brand/50 transition-all"
        >
          Refresh
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-danger-bg border border-danger/30 rounded-lg px-4 py-3" role="alert">
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {/* Loading skeleton */}
      {initialLoading && (
        <div className="animate-pulse space-y-5" aria-hidden="true">
          <div className="h-36 bg-elevated rounded-lg" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-elevated rounded-lg" />
            ))}
          </div>
          <div className="h-48 bg-elevated rounded-lg" />
        </div>
      )}

      {/* Live Metrics */}
      {!initialLoading && liveSession && (
        <div className="bg-elevated border border-live/40 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-live mb-4 flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-live opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-live" />
            </span>
            Live Broadcast
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
            <div>
              <p className="text-xs text-text-muted font-medium uppercase tracking-wider mb-1">Uptime</p>
              <p className="text-2xl font-bold text-text font-mono tracking-tight">
                {formatDuration(
                  liveSession.duration_seconds +
                    Math.floor(Date.now() / 1000 - liveSession.started_at)
                )}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted font-medium uppercase tracking-wider mb-1">Peak Viewers</p>
              <p className="text-2xl font-bold text-text font-mono tracking-tight">
                {liveSession.peak_viewers}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted font-medium uppercase tracking-wider mb-1">Avg Viewers</p>
              <p className="text-2xl font-bold text-text font-mono tracking-tight">
                {liveSession.avg_viewers}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted font-medium uppercase tracking-wider mb-1">Chat Messages</p>
              <p className="text-2xl font-bold text-text font-mono tracking-tight">
                {liveSession.total_chat_messages}
              </p>
            </div>
          </div>
          {liveSession.platforms.length > 0 && (
            <div className="mt-3 flex gap-1.5">
              {liveSession.platforms.map((p) => (
                <span
                  key={p}
                  className="px-2.5 py-1 rounded-md bg-hover border border-border text-xs text-text-secondary font-mono"
                >
                  {p}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Totals overview */}
      {!initialLoading && totals && totals.total_sessions > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-elevated border border-border rounded-lg p-4">
            <p className="text-xs text-text-muted font-medium uppercase tracking-wider mb-1">
              Total Broadcasts
            </p>
            <p className="text-2xl font-bold text-text font-mono tracking-tight">
              {totals.total_sessions}
            </p>
          </div>
          <div className="bg-elevated border border-border rounded-lg p-4">
            <p className="text-xs text-text-muted font-medium uppercase tracking-wider mb-1">
              Total Messages
            </p>
            <p className="text-2xl font-bold text-text font-mono tracking-tight">
              {totals.total_messages}
            </p>
          </div>
          <div className="bg-elevated border border-border rounded-lg p-4">
            <p className="text-xs text-text-muted font-medium uppercase tracking-wider mb-1">
              Total Hours
            </p>
            <p className="text-2xl font-bold text-text font-mono tracking-tight">
              {totals.total_duration_hours}
            </p>
          </div>
          <div className="bg-elevated border border-border rounded-lg p-4">
            <p className="text-xs text-text-muted font-medium uppercase tracking-wider mb-1">
              All-Time Peak
            </p>
            <p className="text-2xl font-bold text-text font-mono tracking-tight">
              {totals.all_time_peak}
            </p>
          </div>
        </div>
      )}

      {/* Session History */}
      <div className="bg-elevated border border-border rounded-lg p-5">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3.5">
          Session History
        </h3>
        {!initialLoading && recentSessions.length === 0 ? (
          <p className="text-sm text-text-muted">No broadcasts yet.</p>
        ) : (
          <div className="space-y-2">
            {recentSessions.map((s) => (
              <div
                key={s.id}
                className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                  selectedSession === s.id
                    ? "border-brand/50 bg-hover"
                    : "border-border/60 bg-surface hover:bg-hover hover:border-border"
                }`}
                onClick={() => handleSelectSession(s.id)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleSelectSession(s.id); } }}
                role="button"
                tabIndex={0}
                aria-label={`Session from ${formatDate(s.started_at)}`}
              >
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium text-text">{formatDate(s.started_at)}</p>
                    <p className="text-xs text-text-muted font-mono">
                      {formatDuration(s.duration_seconds)} &middot; {s.peak_viewers} peak &middot;{" "}
                      {s.total_chat_messages} msgs
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {s.status === "live" && (
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-live/15 text-live border border-live/30">
                        LIVE
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownloadCsv(s.id);
                      }}
                      className="px-2.5 py-1 text-xs font-medium border border-border rounded-lg text-text-secondary bg-hover hover:bg-elevated hover:text-text focus:outline-none focus:ring-2 focus:ring-brand/50 transition-all"
                      aria-label={`Download CSV for session from ${formatDate(s.started_at)}`}
                    >
                      CSV
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Report Viewer */}
      {selectedSession && report && (
        <div className="bg-elevated border border-border rounded-lg p-5 space-y-5">
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Session Report
          </h3>

          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Duration</p>
              <p className="text-lg font-bold text-text font-mono">
                {formatDuration(report.summary.duration_seconds)}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Peak Viewers</p>
              <p className="text-lg font-bold text-text font-mono">{report.summary.peak_viewers}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Avg Viewers</p>
              <p className="text-lg font-bold text-text font-mono">{report.summary.avg_viewers}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Platforms</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {report.summary.platforms.map((p) => (
                  <span
                    key={p}
                    className="px-2 py-0.5 rounded bg-hover text-text-muted text-xs border border-border/50 font-mono"
                  >
                    {p}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <hr className="border-border/50" />

          {/* Engagement */}
          <div>
            <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
              Engagement
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Chat Messages</p>
                <p className="text-lg font-bold text-text font-mono">
                  {report.engagement.total_chat_messages}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Unique Chatters</p>
                <p className="text-lg font-bold text-text font-mono">
                  {report.engagement.unique_chatters}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Msgs/Minute</p>
                <p className="text-lg font-bold text-text font-mono">
                  {report.engagement.messages_per_minute}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Polls / Assets</p>
                <p className="text-lg font-bold text-text font-mono">
                  {report.engagement.polls_conducted} / {report.engagement.assets_created}
                </p>
              </div>
            </div>
          </div>

          {/* Top Chatters */}
          {report.engagement.top_chatters.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2.5">
                Top Chatters
              </h4>
              <div className="space-y-1">
                {report.engagement.top_chatters.map((c, i) => (
                  <div
                    key={i}
                    className="flex justify-between text-sm px-3 py-2 bg-surface border border-border/50 rounded-lg"
                  >
                    <span className="text-text">
                      <span className="text-text-muted font-mono mr-2">#{i + 1}</span>
                      {c.user}
                    </span>
                    <span className="text-text-muted font-mono text-xs">{c.count} messages</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Event Timeline */}
          {report.timeline.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2.5">
                Event Timeline
              </h4>
              <div className="max-h-64 overflow-y-auto space-y-1 pr-1 scrollbar-thin">
                {report.timeline.map((evt) => (
                  <div
                    key={evt.id}
                    className="flex gap-3 text-sm py-2 px-3 border-b border-border/30 last:border-0 bg-surface/50 rounded-sm"
                  >
                    <span className="text-text-muted font-mono whitespace-nowrap text-xs mt-0.5">
                      {new Date(evt.timestamp * 1000).toLocaleTimeString()}
                    </span>
                    <span className="font-medium text-text">{evt.event_type}</span>
                    {evt.event_type === "scene.switched" && (
                      <span className="text-text-muted">
                        &rarr; {String(evt.payload.scene ?? "")}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {selectedSession && !report && !loading && !initialLoading && (
        <p className="text-sm text-text-muted">Select a session to view its report.</p>
      )}

      {loading && selectedSession && (
        <div className="bg-elevated border border-border rounded-lg p-5 animate-pulse space-y-4" aria-hidden="true">
          <div className="h-4 w-32 bg-hover rounded" />
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 bg-hover rounded" />
            ))}
          </div>
          <div className="h-4 w-24 bg-hover rounded" />
          <div className="h-32 bg-hover rounded" />
        </div>
      )}
    </div>
  );
}
