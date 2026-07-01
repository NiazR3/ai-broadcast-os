import { useState, useEffect } from "react";
import {
  createEpisode, listEpisodes, addSegment,
  loadEpisode, getDirectorStatus, directorNext, generateDialogue,
} from "../lib/api";
import type { EpisodeScript, DirectorStatus } from "../lib/api";

export function AgentPanel() {
  const [episodes, setEpisodes] = useState<EpisodeScript[]>([]);
  const [director, setDirector] = useState<DirectorStatus | null>(null);
  const [title, setTitle] = useState("");
  const [segTitle, setSegTitle] = useState("");
  const [segType, setSegType] = useState("content");
  const [selectedEp, setSelectedEp] = useState<string | null>(null);
  const [dialogue, setDialogue] = useState<{ host: string; cohost: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchEpisodes = async () => {
    try { setEpisodes(await listEpisodes()); } catch { /* ignore */ }
  };
  const fetchDirector = async () => {
    try { setDirector(await getDirectorStatus()); } catch { /* ignore */ }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([fetchEpisodes(), fetchDirector()]);
      setLoading(false);
    };
    load();
  }, []);

  const handleCreate = async () => {
    if (!title.trim()) return;
    setError(null);
    try {
      await createEpisode(title.trim());
      setTitle("");
      await fetchEpisodes();
    } catch { setError("Failed to create episode"); }
  };

  const handleAddSegment = async () => {
    if (!selectedEp || !segTitle.trim()) return;
    setError(null);
    try {
      const id = `seg_${Date.now()}`;
      await addSegment(selectedEp, { id, type: segType, title: segTitle.trim(), duration_seconds: 30 });
      setSegTitle("");
      await fetchEpisodes();
    } catch { setError("Failed to add segment"); }
  };

  const handleLoad = async (epId: string) => {
    setError(null);
    try {
      await loadEpisode(epId);
      setSelectedEp(epId);
      await fetchDirector();
    } catch { setError("Failed to load episode"); }
  };

  const handleNext = async () => {
    setError(null);
    setDialogue(null);
    try {
      await directorNext();
      await fetchDirector();
    } catch { setError("No more segments"); }
  };

  const handleGenerate = async () => {
    setError(null);
    try {
      const d = await generateDialogue();
      setDialogue({
        host: d.host.lines.map(l => l.text).join(" "),
        cohost: d.cohost.lines.map(l => l.text).join(" "),
      });
    } catch { setError("Failed to generate dialogue"); }
  };

  return (
    <div className="space-y-5">
      {/* ── Section Header ── */}
      <div className="section-header">
        <div>
          <h3 className="section-header__title">Director Controls</h3>
          <p className="section-header__subtitle">Episode workflow and agent direction</p>
        </div>
      </div>

      {/* ── Director Status Card ── */}
      <div className="card">
        {loading ? (
          <div className="space-y-3" aria-hidden="true">
            <div className="flex items-center gap-3">
              <div className="h-3 w-3 rounded-full bg-border animate-pulse" />
              <div className="h-3 w-24 rounded bg-border animate-pulse" />
              <div className="h-5 w-20 rounded bg-border animate-pulse ml-auto" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="h-3 w-12 rounded bg-border animate-pulse" />
                <div className="h-4 w-32 rounded bg-border animate-pulse" />
              </div>
              <div className="space-y-2">
                <div className="h-3 w-12 rounded bg-border animate-pulse" />
                <div className="h-4 w-32 rounded bg-border animate-pulse" />
              </div>
            </div>
          </div>
        ) : director ? (
          <div className="space-y-4">
            {/* Status header row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className={`live-dot ${director.running ? "" : "live-dot--off"}`} />
                <span
                  className={`text-xs font-semibold uppercase tracking-widest ${
                    director.running ? "text-live" : "text-text-muted"
                  }`}
                >
                  {director.running ? "Running" : "Idle"}
                </span>
              </div>
              <span className="badge badge--default">
                {director.script_title || "No Script"}
              </span>
            </div>

            {/* Metrics grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="metric-card">
                <span className="metric-card__label">Script</span>
                <span className="text-sm font-medium text-text truncate">
                  {director.script_title || "None loaded"}
                </span>
              </div>
              <div className="metric-card">
                <span className="metric-card__label">Current Segment</span>
                <span className="text-sm font-medium text-text truncate">
                  {director.current_segment?.title || "None"}
                </span>
              </div>
            </div>

            {/* Remaining indicator */}
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 text-xs ${
                  director.has_more ? "text-text-secondary" : "text-warning"
                }`}
              >
                <span
                  className={`inline-block h-1.5 w-1.5 rounded-full ${
                    director.has_more ? "bg-text-muted" : "bg-warning"
                  }`}
                />
                {director.has_more ? "More segments remaining" : "End of show"}
              </span>
            </div>

            {/* Action Controls */}
            <div className="flex gap-2 pt-1">
              <button onClick={handleNext} className="btn btn-primary">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
                </svg>
                Next Segment
              </button>
              <button onClick={handleGenerate} className="btn btn-ghost">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                Generate Dialogue
              </button>
            </div>

            {/* Dialogue Display */}
            {dialogue && (
              <div className="animate-fade-in-down space-y-3 border-t border-border pt-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                  Generated Dialogue
                </h4>
                <div className="border-l-2 border-brand pl-3">
                  <p className="mb-0.5 text-xs font-semibold text-brand">Host</p>
                  <p className="text-sm leading-relaxed text-text">{dialogue.host}</p>
                </div>
                <div className="border-l-2 border-info pl-3">
                  <p className="mb-0.5 text-xs font-semibold text-info">Co-Host</p>
                  <p className="text-sm leading-relaxed text-text">{dialogue.cohost}</p>
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-text-muted">Director status unavailable</p>
        )}
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="animate-fade-in-down flex items-center gap-2.5 rounded-lg border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger" role="alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0" aria-hidden="true">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {error}
        </div>
      )}

      {/* ── Create Episode ── */}
      <div className="card">
        <h4 className="mb-3 text-sm font-semibold text-text" id="create-episode-heading">New Episode</h4>
        <div className="flex gap-2" role="group" aria-labelledby="create-episode-heading">
          <div className="flex-1">
            <label htmlFor="episode-title-input" className="sr-only">Episode title</label>
            <input
              id="episode-title-input"
              type="text"
              value={title}
              placeholder="Episode title..."
              onChange={e => setTitle(e.target.value)}
              className="input-field"
            />
          </div>
          <button onClick={handleCreate} className="btn btn-primary">
            Create
          </button>
        </div>
      </div>

      {/* ── Add Segment (visible only when an episode is loaded) ── */}
      {selectedEp && (
        <div className="card animate-fade-in">
          <h4 className="mb-3 text-sm font-semibold text-text" id="add-segment-heading">Add Segment</h4>
          <div className="flex gap-2" role="group" aria-labelledby="add-segment-heading">
            <div>
              <label htmlFor="segment-type-select" className="sr-only">Segment type</label>
              <select
                id="segment-type-select"
                value={segType}
                onChange={e => setSegType(e.target.value)}
                className="input-field w-32 shrink-0"
              >
                <option value="intro">Intro</option>
                <option value="content">Content</option>
                <option value="guest">Guest</option>
                <option value="ad">Ad</option>
                <option value="outro">Outro</option>
              </select>
            </div>
            <div className="flex-1">
              <label htmlFor="segment-title-input" className="sr-only">Segment title</label>
              <input
                id="segment-title-input"
                type="text"
                value={segTitle}
                placeholder="Segment title..."
                onChange={e => setSegTitle(e.target.value)}
                className="input-field"
              />
            </div>
            <button onClick={handleAddSegment} className="btn btn-primary">
              Add
            </button>
          </div>
        </div>
      )}

      {/* ── Episode List ── */}
      <div className="card">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold text-text">Episodes</h4>
          {!loading && (
            <span className="text-xs text-text-muted">
              <span className="data-value">{episodes.length}</span> total
            </span>
          )}
        </div>

        <div className="-mx-2 max-h-48 space-y-0.5 overflow-y-auto">
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-3" aria-hidden="true">
                <div className="h-4 w-4 shrink-0 rounded bg-border animate-pulse" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 w-3/4 rounded bg-border animate-pulse" />
                  <div className="h-2 w-1/3 rounded bg-border animate-pulse" />
                </div>
              </div>
            ))
          ) : episodes.length === 0 ? (
            <p className="py-8 text-center text-sm text-text-muted">
              No episodes yet. Create one above.
            </p>
          ) : (
            episodes.map(ep => (
              <div
                key={ep.id}
                className={`flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 transition-all duration-150 ${
                  selectedEp === ep.id
                    ? "border border-brand/30 bg-brand/10"
                    : "border border-transparent hover:bg-bg-hover"
                }`}
                onClick={() => handleLoad(ep.id)}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") handleLoad(ep.id); }}
                tabIndex={0}
                role="button"
                aria-current={selectedEp === ep.id ? "true" : undefined}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text">
                    {ep.title}
                  </p>
                  <p className="mt-0.5 text-xs text-text-muted">
                    <span className="data-value">{ep.segments.length}</span> segments
                    <span className="mx-1.5">&middot;</span>
                    {ep.status}
                  </p>
                </div>
                <div className="ml-3 flex shrink-0 items-center gap-2">
                  {selectedEp === ep.id && (
                    <span className="badge badge--brand">Loaded</span>
                  )}
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-text-muted">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
