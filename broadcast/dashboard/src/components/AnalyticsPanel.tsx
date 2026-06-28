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
  BroadcastSession,
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Analytics</h2>
        <button
          onClick={fetchData}
          className="px-3 py-1 text-sm rounded bg-gray-100 hover:bg-gray-200"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 rounded-lg border border-red-200">
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Live Metrics */}
      {liveSession && (
        <div className="bg-white rounded-lg shadow-sm p-6 border border-green-200">
          <h3 className="text-lg font-semibold text-green-700 mb-3">
            ● Live Broadcast
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-500">Uptime</p>
              <p className="text-xl font-bold">
                {formatDuration(liveSession.duration_seconds +
                  Math.floor((Date.now() / 1000) - liveSession.started_at))}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Peak Viewers</p>
              <p className="text-xl font-bold">{liveSession.peak_viewers}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Avg Viewers</p>
              <p className="text-xl font-bold">{liveSession.avg_viewers}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Chat Messages</p>
              <p className="text-xl font-bold">{liveSession.total_chat_messages}</p>
            </div>
          </div>
          {liveSession.platforms.length > 0 && (
            <div className="mt-2 flex gap-2">
              {liveSession.platforms.map((p) => (
                <span key={p} className="px-2 py-0.5 rounded bg-gray-100 text-xs text-gray-600">
                  {p}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Totals overview */}
      {totals && totals.total_sessions > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow-sm p-4">
            <p className="text-sm text-gray-500">Total Broadcasts</p>
            <p className="text-2xl font-bold">{totals.total_sessions}</p>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4">
            <p className="text-sm text-gray-500">Total Messages</p>
            <p className="text-2xl font-bold">{totals.total_messages}</p>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4">
            <p className="text-sm text-gray-500">Total Hours</p>
            <p className="text-2xl font-bold">{totals.total_duration_hours}</p>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-4">
            <p className="text-sm text-gray-500">All-Time Peak</p>
            <p className="text-2xl font-bold">{totals.all_time_peak}</p>
          </div>
        </div>
      )}

      {/* Session History */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold mb-3">Session History</h3>
        {recentSessions.length === 0 ? (
          <p className="text-sm text-gray-400">No broadcasts yet.</p>
        ) : (
          <div className="space-y-2">
            {recentSessions.map((s) => (
              <div
                key={s.id}
                className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                  selectedSession === s.id
                    ? "border-blue-400 bg-blue-50"
                    : "border-gray-200 hover:bg-gray-50"
                }`}
                onClick={() => handleSelectSession(s.id)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">
                      {formatDate(s.started_at)}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatDuration(s.duration_seconds)} &middot; {s.peak_viewers} peak viewers &middot; {s.total_chat_messages} messages
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {s.status === "live" && (
                      <span className="px-2 py-0.5 rounded bg-green-100 text-green-700 text-xs">
                        LIVE
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownloadCsv(s.id);
                      }}
                      className="px-2 py-1 text-xs rounded bg-gray-100 hover:bg-gray-200"
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
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold mb-3">Session Report</h3>

          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div>
              <p className="text-sm text-gray-500">Duration</p>
              <p className="text-lg font-bold">
                {formatDuration(report.summary.duration_seconds)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Peak Viewers</p>
              <p className="text-lg font-bold">{report.summary.peak_viewers}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Avg Viewers</p>
              <p className="text-lg font-bold">{report.summary.avg_viewers}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Platforms</p>
              <div className="flex flex-wrap gap-1">
                {report.summary.platforms.map((p) => (
                  <span key={p} className="px-2 py-0.5 rounded bg-gray-100 text-xs">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Engagement */}
          <h4 className="font-medium text-gray-700 mb-2">Engagement</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div>
              <p className="text-sm text-gray-500">Chat Messages</p>
              <p className="text-lg font-bold">{report.engagement.total_chat_messages}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Unique Chatters</p>
              <p className="text-lg font-bold">{report.engagement.unique_chatters}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Msgs/Minute</p>
              <p className="text-lg font-bold">{report.engagement.messages_per_minute}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Polls / Assets</p>
              <p className="text-lg font-bold">
                {report.engagement.polls_conducted} / {report.engagement.assets_created}
              </p>
            </div>
          </div>

          {/* Top Chatters */}
          {report.engagement.top_chatters.length > 0 && (
            <div className="mb-6">
              <h4 className="font-medium text-gray-700 mb-2">Top Chatters</h4>
              <div className="space-y-1">
                {report.engagement.top_chatters.map((c, i) => (
                  <div key={i} className="flex justify-between text-sm">
                    <span>#{i + 1} {c.user}</span>
                    <span className="text-gray-500">{c.count} messages</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Event Timeline */}
          {report.timeline.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Event Timeline</h4>
              <div className="max-h-64 overflow-y-auto space-y-1">
                {report.timeline.map((evt) => (
                  <div
                    key={evt.id}
                    className="flex gap-3 text-sm py-1 border-b border-gray-100 last:border-0"
                  >
                    <span className="text-gray-400 whitespace-nowrap">
                      {new Date(evt.timestamp * 1000).toLocaleTimeString()}
                    </span>
                    <span className="font-medium text-gray-600">{evt.event_type}</span>
                    {evt.event_type === "scene.switched" && (
                      <span className="text-gray-500">
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

      {selectedSession && !report && !loading && (
        <p className="text-sm text-gray-400">Select a session to view its report.</p>
      )}

      {loading && selectedSession && (
        <p className="text-sm text-gray-400">Loading report...</p>
      )}
    </div>
  );
}
