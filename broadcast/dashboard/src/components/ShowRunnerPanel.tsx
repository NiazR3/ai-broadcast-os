import { useState, useEffect, useCallback } from "react";
import {
  produceShow,
  runShow,
  getShowStatus,
  resetShowRunner,
  prepareRun,
  connectObs,
  nextSegment,
  seekSegment,
  completeRun,
  abortRun,
  getRunState,
} from "../lib/api";
import type {
  ShowProductionResult,
  ShowSegmentResult,
  ShowStatus,
  RunState,
} from "../lib/api";
import { useWebSocket } from "../hooks/useWebSocket";

const SHOW_CATEGORIES = [
  "general",
  "technology",
  "science",
  "sports",
  "entertainment",
  "health",
  "business",
  "politics",
  "weather",
];

export function ShowRunnerPanel() {
  const { lastEvent } = useWebSocket();
  const [topic, setTopic] = useState("");
  const [category, setCategory] = useState("general");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<ShowStatus | null>(null);
  const [productionResult, setProductionResult] = useState<ShowProductionResult | null>(null);
  const [runLog, setRunLog] = useState<string[]>([]);
  const [segmentResults, setSegmentResults] = useState<ShowSegmentResult[]>([]);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [interactiveMode, setInteractiveMode] = useState(false);
  const [expandedSegments, setExpandedSegments] = useState<Set<string>>(new Set());
  const [liveEvent, setLiveEvent] = useState<string | null>(null);
  const [showRunLog, setShowRunLog] = useState(false);

  // Poll status on mount
  const fetchStatus = useCallback(async () => {
    try {
      const s = await getShowStatus();
      setStatus(s);
    } catch {
      // Silent — initial poll may fail
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Track live show events from WebSocket
  useEffect(() => {
    if (!lastEvent) return;
    const type = lastEvent.type;
    if (type.startsWith("show.")) {
      setLiveEvent(`${type}: ${JSON.stringify(lastEvent).slice(0, 80)}`);
      if (type === "show.segment.completed") {
        setRunLog((prev) => [
          ...prev,
          `Segment completed: ${lastEvent.segment_id}`,
        ]);
      } else if (type === "show.segment.started") {
        setRunLog((prev) => [
          ...prev,
          `Segment started: ${lastEvent.segment_id} (${lastEvent.segment_type})`,
        ]);
      } else if (type === "show.completed") {
        setRunLog((prev) => [...prev, "Show completed"]);
      } else if (type === "show.failed") {
        setRunLog((prev) => [...prev, `Show failed: ${lastEvent.error}`]);
      }
    }
  }, [lastEvent?.type, lastEvent?.timestamp]);

  const handleProduce = async () => {
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    setProductionResult(null);
    setSegmentResults([]);
    setRunLog([]);
    setLiveEvent(null);
    try {
      const result = await produceShow(topic.trim(), category);
      setProductionResult(result);
      setRunLog(result.production_log || []);
      await fetchStatus();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Production failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRunOneShot = async () => {
    setRunning(true);
    setError(null);
    setInteractiveMode(false);
    try {
      const result = await runShow(productionResult?.episode_id);
      setSegmentResults(result.segment_results || []);
      setRunLog((prev) => [...prev, ...(result.run_log || [])]);
      await fetchStatus();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(false);
    }
  };

  const handlePrepareInteractive = async () => {
    setRunning(true);
    setError(null);
    try {
      const result = await prepareRun(productionResult?.episode_id);
      setInteractiveMode(true);
      setRunLog((prev) => [...prev, `Interactive run prepared (${result.total_segments} segments)`]);
      await getRunState().then(setRunState);
      // Best-effort OBS connect
      connectObs().then((obs) => {
        setRunLog((prev) => [
          ...prev,
          obs.obs_connected ? "OBS connected" : "OBS not available",
        ]);
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Prepare failed");
    } finally {
      setRunning(false);
    }
  };

  const handleNextSegment = async () => {
    setError(null);
    try {
      const result = await nextSegment();
      setRunLog((prev) => [
        ...prev,
        `Segment ${result.segment_index + 1}: ${result.segment.segment_title} (${result.segment.segment_type})`,
      ]);
      await getRunState().then(setRunState);
      if (!result.has_more) {
        setRunLog((prev) => [...prev, "All segments played — complete or abort"]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to advance");
    }
  };

  const handleSeek = async (segmentId: string) => {
    setError(null);
    try {
      await seekSegment(segmentId);
      setRunLog((prev) => [...prev, `Sought to segment: ${segmentId}`]);
      await getRunState().then(setRunState);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Seek failed");
    }
  };

  const handleComplete = async () => {
    setError(null);
    try {
      const result = await completeRun();
      setSegmentResults(result.segment_results || []);
      setInteractiveMode(false);
      setRunLog((prev) => [...prev, "Run completed"]);
      await fetchStatus();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Complete failed");
    }
  };

  const handleAbort = async () => {
    setError(null);
    try {
      const result = await abortRun();
      setSegmentResults(result.segment_results || []);
      setInteractiveMode(false);
      setRunLog((prev) => [...prev, "Run aborted"]);
      await fetchStatus();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Abort failed");
    }
  };

  const handleReset = async () => {
    setError(null);
    setProductionResult(null);
    setSegmentResults([]);
    setRunLog([]);
    setRunState(null);
    setInteractiveMode(false);
    setLiveEvent(null);
    try {
      await resetShowRunner();
      await fetchStatus();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  };

  const toggleSegment = (id: string) => {
    setExpandedSegments((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const isReady = status?.state === "ready";
  const isLoading = loading || running;

  return (
    <div className="bg-surface border border-border rounded-lg p-6">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-text uppercase tracking-[0.08em]">
          Show Runner
        </h2>
        <span
          className={`text-xs font-mono px-2 py-0.5 rounded-full border ${
            status?.state === "idle"
              ? "text-text-muted border-border bg-elevated"
              : status?.state === "ready"
              ? "text-brand border-brand/30 bg-brand-muted/15"
              : status?.state === "running"
              ? "text-live border-live/30 bg-live/10"
              : status?.state === "completed"
              ? "text-green-400 border-green-400/30 bg-green-400/10"
              : status?.state === "failed"
              ? "text-danger border-danger/30 bg-danger-bg"
              : "text-text-muted border-border"
          }`}
        >
          {status?.state || "unknown"}
        </span>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-danger-bg border border-danger/30 rounded-lg px-4 py-3 mb-4" role="alert">
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {/* Live event badge */}
      {liveEvent && (
        <div className="bg-brand-muted/10 border border-brand/20 rounded-lg px-3 py-2 mb-4">
          <p className="text-xs text-brand font-mono truncate">{liveEvent}</p>
        </div>
      )}

      {/* ── Produce Section ── */}
      <div className="mb-5">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
          Produce a Show
        </h3>
        <div className="flex gap-2 mb-2">
          <div className="flex-1">
            <label htmlFor="show-topic" className="sr-only">Show topic</label>
            <input
              id="show-topic"
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleProduce())}
              placeholder="Enter a show topic..."
              disabled={isLoading}
              className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all disabled:opacity-40"
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            disabled={isLoading}
            className="px-3 py-2.5 bg-base border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40"
          >
            {SHOW_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </option>
            ))}
          </select>
          <button
            onClick={handleProduce}
            disabled={isLoading || !topic.trim()}
            className="px-4 py-2.5 bg-brand hover:bg-brand-hover text-white rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Producing
              </span>
            ) : (
              "Produce"
            )}
          </button>
        </div>
      </div>

      {/* ── Production Result ── */}
      {productionResult && (
        <div className="bg-elevated border border-border rounded-lg p-4 mb-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-text-muted block">Episode</span>
              <span className="text-text font-mono">{productionResult.episode_id}</span>
            </div>
            <div>
              <span className="text-text-muted block">Segments</span>
              <span className="text-text font-medium">{productionResult.segments}</span>
            </div>
            <div>
              <span className="text-text-muted block">Duration</span>
              <span className="text-text font-medium">
                {Math.floor(productionResult.total_duration_seconds / 60)}m{" "}
                {productionResult.total_duration_seconds % 60}s
              </span>
            </div>
            <div>
              <span className="text-text-muted block">Assets</span>
              <span className="text-text font-medium">{productionResult.assets_created}</span>
            </div>
            <div>
              <span className="text-text-muted block">Research</span>
              <span className="text-text font-medium">{productionResult.research_count}</span>
            </div>
            <div>
              <span className="text-text-muted block">Dialogue</span>
              <span className="text-text font-medium">{productionResult.dialogue_generated}</span>
            </div>
            <div>
              <span className="text-text-muted block">Poll</span>
              <span className="text-text font-mono">{productionResult.poll_id || "—"}</span>
            </div>
            <div>
              <span className="text-text-muted block">Produced in</span>
              <span className="text-text font-medium">{productionResult.production_time_seconds}s</span>
            </div>
          </div>
          {productionResult.personas.host && (
            <div className="mt-3 flex gap-4 text-xs">
              <div>
                <span className="text-text-muted">Host: </span>
                <span className="text-text font-medium">{productionResult.personas.host}</span>
              </div>
              <div>
                <span className="text-text-muted">Co-host: </span>
                <span className="text-text font-medium">{productionResult.personas.cohost}</span>
              </div>
            </div>
          )}

          {/* Run buttons */}
          {isReady && !interactiveMode && (
            <div className="flex gap-2 mt-4 pt-3 border-t border-border">
              <button
                onClick={handleRunOneShot}
                disabled={isLoading}
                className="px-4 py-2 bg-live hover:bg-green-600 text-white rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-live/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                {running ? (
                  <span className="flex items-center gap-2">
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Running
                  </span>
                ) : (
                  "▶ Run (One Shot)"
                )}
              </button>
              <button
                onClick={handlePrepareInteractive}
                disabled={isLoading}
                className="px-4 py-2 bg-hover hover:bg-elevated border border-border text-text-secondary hover:text-text rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                ▶ Step (Interactive)
              </button>
              <button
                onClick={handleReset}
                className="px-3 py-2 text-xs text-text-muted hover:text-danger transition-colors ml-auto"
              >
                Reset
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Interactive Controls ── */}
      {interactiveMode && runState && (
        <div className="bg-elevated border border-brand/20 rounded-lg p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold text-text uppercase tracking-wider">
              Interactive Controls
            </h3>
            <span className="text-xs text-text-muted font-mono">
              {runState.segments_played}/{runState.total_segments} segments
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-1.5 bg-base rounded-full mb-3 overflow-hidden">
            <div
              className="h-full bg-brand rounded-full transition-all duration-300"
              style={{
                width: runState.total_segments > 0
                  ? `${(runState.segments_played / runState.total_segments) * 100}%`
                  : "0%",
              }}
            />
          </div>

          <div className="flex flex-wrap gap-2 mb-3">
            <button
              onClick={handleNextSegment}
              disabled={!runState.has_more || isLoading}
              className="px-4 py-2 bg-brand hover:bg-brand-hover text-white rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {isLoading ? "Loading..." : "▶ Next Segment"}
            </button>
            <button
              onClick={handleComplete}
              className="px-3 py-2 bg-live/20 hover:bg-live/30 text-live rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-live/50 transition-all"
            >
              ✓ Complete
            </button>
            <button
              onClick={handleAbort}
              className="px-3 py-2 bg-danger-bg hover:bg-red-900/30 text-danger rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-danger/50 transition-all"
            >
              ✕ Abort
            </button>
          </div>

          {/* Seek buttons */}
          <div className="flex flex-wrap gap-1.5">
            <span className="text-xs text-text-muted self-center mr-1">Seek:</span>
            {["intro", "content_1", "guest", "ad", "content_2", "outro"].map((segId) => (
              <button
                key={segId}
                onClick={() => handleSeek(segId)}
                disabled={isLoading}
                className="px-2 py-1 bg-base border border-border text-text-secondary hover:text-text text-xs rounded focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40 transition-all"
              >
                {segId.replace("_", " ")}
              </button>
            ))}
          </div>

          {runState.current_segment && (
            <div className="mt-3 text-xs text-text-muted">
              Current: <span className="text-text font-medium font-mono">{runState.current_segment.title}</span>
              {" · "}
              Index: <span className="font-mono">{runState.current_segment_index}</span>
              {" · "}
              Has more: <span className="font-mono">{runState.has_more ? "yes" : "no"}</span>
            </div>
          )}
        </div>
      )}

      {/* ── Segment Results ── */}
      {segmentResults.length > 0 && (
        <div className="mb-5">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
            Segment Results ({segmentResults.length})
          </h3>
          <div className="space-y-2">
            {segmentResults.map((seg) => (
              <div key={seg.segment_id} className="border border-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSegment(seg.segment_id)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-elevated hover:bg-hover transition-colors text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand/50"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-text-muted w-6">
                      {seg.order + 1}
                    </span>
                    <div>
                      <span className="text-sm font-medium text-text">
                        {seg.segment_title}
                      </span>
                      <span className="ml-2 text-xs text-text-muted">
                        {seg.segment_type} · {seg.duration_seconds}s · {seg.scene}
                      </span>
                    </div>
                  </div>
                  <svg
                    className={`w-4 h-4 text-text-muted transition-transform ${
                      expandedSegments.has(seg.segment_id) ? "rotate-180" : ""
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </button>
                {expandedSegments.has(seg.segment_id) && (
                  <div className="px-4 py-3 bg-base border-t border-border space-y-3">
                    {/* Host dialogue */}
                    {seg.host_dialogue.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1.5">
                          Host
                        </h4>
                        {seg.host_dialogue.map((line, i) => (
                          <p key={i} className="text-sm text-text bg-elevated rounded p-2.5 mb-1">
                            {line.text}
                          </p>
                        ))}
                      </div>
                    )}
                    {/* Co-host dialogue */}
                    {seg.cohost_dialogue.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1.5">
                          Co-host
                        </h4>
                        {seg.cohost_dialogue.map((line, i) => (
                          <p key={i} className="text-sm text-text-secondary bg-elevated rounded p-2.5 mb-1">
                            {line.text}
                          </p>
                        ))}
                      </div>
                    )}
                    {seg.host_dialogue.length === 0 && seg.cohost_dialogue.length === 0 && (
                      <p className="text-xs text-text-muted italic">No dialogue generated</p>
                    )}
                    {seg.scene_switched !== undefined && (
                      <p className="text-xs text-text-muted font-mono">
                        Scene switched: {seg.scene_switched ? "yes" : "no"}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Run Log ── */}
      {runLog.length > 0 && (
        <div>
          <button
            onClick={() => setShowRunLog(!showRunLog)}
            className="flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary transition-colors mb-2"
          >
            <svg
              className={`w-3.5 h-3.5 transition-transform ${showRunLog ? "rotate-90" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
            Run Log ({runLog.length} entries)
          </button>
          {showRunLog && (
            <div className="bg-base border border-border rounded-lg max-h-40 overflow-y-auto p-3 font-mono text-xs text-text-muted space-y-1">
              {runLog.map((entry, i) => (
                <p key={i} className="leading-relaxed">
                  <span className="text-text-muted/50">{i + 1}.</span> {entry}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── IDLE state: show status ── */}
      {!productionResult && !isLoading && (
        <div className="flex items-center justify-center h-24 border border-dashed border-border rounded-lg">
          <p className="text-sm text-text-muted">
            {status?.state === "idle"
              ? "Enter a topic and click Produce to start"
              : "No show produced yet"}
          </p>
        </div>
      )}
    </div>
  );
}
