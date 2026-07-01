import { useRef, useEffect, useState } from "react";
import { BroadcastStatus } from "./components/BroadcastStatus";
import { SceneSwitcher } from "./components/SceneSwitcher";
import { ConfigPanel } from "./components/ConfigPanel";
import { AgentPanel } from "./components/AgentPanel";
import { Teleprompter } from "./components/Teleprompter";
import { PersonaPanel } from "./components/PersonaPanel";
import { ChatPanel } from "./components/ChatPanel";
import { PollPanel } from "./components/PollPanel";
import { ResearchPanel } from "./components/ResearchPanel";
import { MediaPanel } from "./components/MediaPanel";
import { ShowRunnerPanel } from "./components/ShowRunnerPanel";
import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { useWebSocket } from "./hooks/useWebSocket";
import { Sidebar } from "./components/Sidebar";

function App() {
  const { lastEvent } = useWebSocket();
  const [isLive, setIsLive] = useState(false);
  const [uptimeSeconds, setUptimeSeconds] = useState(0);
  const liveStartRef = useRef<number | null>(null);
  const uptimeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Track live state from WebSocket events
  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.type === "broadcast.started") {
      setIsLive(true);
      liveStartRef.current = Date.now();
      setUptimeSeconds(0);
      // Start uptime counter
      if (uptimeIntervalRef.current) clearInterval(uptimeIntervalRef.current);
      uptimeIntervalRef.current = setInterval(() => {
        if (liveStartRef.current) {
          setUptimeSeconds(Math.floor((Date.now() - liveStartRef.current) / 1000));
        }
      }, 1000);
    } else if (lastEvent.type === "broadcast.stopped") {
      setIsLive(false);
      liveStartRef.current = null;
      setUptimeSeconds(0);
      if (uptimeIntervalRef.current) {
        clearInterval(uptimeIntervalRef.current);
        uptimeIntervalRef.current = null;
      }
    }
  }, [lastEvent?.type, lastEvent?.timestamp]);

  // Cleanup uptime interval on unmount
  useEffect(() => {
    return () => {
      if (uptimeIntervalRef.current) clearInterval(uptimeIntervalRef.current);
    };
  }, []);

  const formatBarUptime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex min-h-screen bg-bg-base">
      {/* ---- Fixed sidebar ---- */}
      <Sidebar isLive={isLive} />

      {/* ---- Main area (pushed right by sidebar width) ---- */}
      <div className="ml-14 flex flex-1 flex-col">
        {/* ---- Top header bar ---- */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-bg-elevated px-6">
          <div className="flex items-center gap-3">
            <span className="text-base font-semibold tracking-widest text-text">
              BROADCAST OS
            </span>
            {isLive ? (
              <span className="flex items-center gap-1.5" title="Live" role="status" aria-label="Broadcast is live">
                <span className="live-dot" />
                <span className="text-xs font-semibold text-live uppercase tracking-wider">LIVE</span>
                {uptimeSeconds > 0 && (
                  <span className="text-xs font-mono text-live tabular-nums">
                    {formatBarUptime(uptimeSeconds)}
                  </span>
                )}
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-text-muted" title="Offline" role="status" aria-label="Broadcast is offline">
                <span className="live-dot live-dot--off" />
                <span className="text-xs font-medium">Offline</span>
              </span>
            )}
          </div>

          {lastEvent && (
            <span className="max-w-80 truncate text-xs text-text-secondary" aria-live="polite">
              Last event: {lastEvent.type}
              {lastEvent.scene && ` → ${lastEvent.scene}`}
            </span>
          )}
        </header>

        {/* ---- Scrollable content ---- */}
        <main className="flex-1 overflow-y-auto p-6 pb-16">
          <div className="mx-auto max-w-7xl space-y-8">
            {/* ---------- Broadcast ---------- */}
            <section id="section-broadcast">
              <div className="section-header">
                <div>
                  <h2 className="section-header__title">Broadcast Studio</h2>
                  <p className="section-header__subtitle">
                    Live production control
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="card">
                  <BroadcastStatus />
                </div>
                <div className="card">
                  <SceneSwitcher />
                </div>
                <div className="card">
                  <ConfigPanel />
                </div>
              </div>
            </section>

            {/* ---------- Teleprompter ---------- */}
            <section id="section-teleprompter">
              <div className="section-header">
                <div>
                  <h2 className="section-header__title">Teleprompter</h2>
                  <p className="section-header__subtitle">Script delivery</p>
                </div>
              </div>

              <div className="card">
                <Teleprompter />
              </div>
            </section>

            {/* ---------- Show Production ---------- */}
            <section id="section-show">
              <div className="section-header">
                <div>
                  <h2 className="section-header__title">Show Production</h2>
                  <p className="section-header__subtitle">
                    Episode orchestration
                  </p>
                </div>
              </div>

              <div className="card">
                <ShowRunnerPanel />
              </div>
            </section>

            {/* ---------- Agents ---------- */}
            <section id="section-agents">
              <div className="section-header">
                <div>
                  <h2 className="section-header__title">
                    Agent Management
                  </h2>
                  <p className="section-header__subtitle">
                    Director, personas &amp; routing
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="card">
                  <AgentPanel />
                </div>
                <div className="card">
                  <PersonaPanel />
                </div>
              </div>
            </section>

            {/* ---------- Audience ---------- */}
            <section id="section-audience">
              <div className="section-header">
                <div>
                  <h2 className="section-header__title">Audience</h2>
                  <p className="section-header__subtitle">Chat &amp; polls</p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="card">
                  <ChatPanel />
                </div>
                <div className="card">
                  <PollPanel />
                </div>
              </div>
            </section>

            {/* ---------- Research ---------- */}
            <section id="section-research">
              <div className="section-header">
                <div>
                  <h2 className="section-header__title">Research Engine</h2>
                  <p className="section-header__subtitle">
                    Content intelligence
                  </p>
                </div>
              </div>

              <div className="card">
                <ResearchPanel />
              </div>
            </section>

            {/* ---------- Media ---------- */}
            <section id="section-media">
              <div className="section-header">
                <div>
                  <h2 className="section-header__title">Media Assets</h2>
                  <p className="section-header__subtitle">
                    Scenes &amp; overlays
                  </p>
                </div>
              </div>

              <div className="card">
                <MediaPanel />
              </div>
            </section>

            {/* ---------- Analytics ---------- */}
            <section id="section-analytics">
              <div className="section-header">
                <div>
                  <h2 className="section-header__title">Analytics</h2>
                  <p className="section-header__subtitle">
                    Performance metrics
                  </p>
                </div>
              </div>

              <div className="card">
                <AnalyticsPanel />
              </div>
            </section>
          </div>
        </main>

        {/* ---- Sticky Bottom Status Bar ---- */}
        <footer className="fixed bottom-0 left-14 right-0 z-40 flex h-8 items-center justify-between border-t border-border bg-bg-elevated px-4 text-xs text-text-muted">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              {isLive ? (
                <>
                  <span className="live-dot live-dot--sm" />
                  <span className="font-medium text-live">LIVE</span>
                </>
              ) : (
                <>
                  <span className="live-dot live-dot--sm live-dot--off" />
                  <span>Offline</span>
                </>
              )}
            </span>
            {isLive && uptimeSeconds > 0 && (
              <span className="font-mono tabular-nums">
                {formatBarUptime(uptimeSeconds)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-text-muted">Broadcast OS</span>
            {lastEvent && (
              <span className="text-text-muted/60">
                {(lastEvent as { type: string }).type}
              </span>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
