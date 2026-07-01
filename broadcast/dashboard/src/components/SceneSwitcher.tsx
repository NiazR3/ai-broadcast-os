import { useState, useEffect, useCallback, useRef } from "react";
import { getScenes, switchScene, getSceneSources, toggleSource } from "../lib/api";
import type { SceneSource } from "../lib/api";

const TRANSITIONS = [
  { value: "cut", label: "Cut" },
  { value: "mix", label: "Mix" },
  { value: "fade", label: "Fade" },
] as const;

type TransitionType = (typeof TRANSITIONS)[number]["value"];

/* Different accent hues for scene card visual variety */
const CARD_ACCENTS = [
  { border: "var(--color-brand)", bg: "rgba(99, 102, 241, 0.08)" },
  { border: "var(--color-info)", bg: "rgba(59, 130, 246, 0.08)" },
  { border: "var(--color-accent)", bg: "rgba(249, 115, 22, 0.08)" },
  { border: "var(--color-live)", bg: "rgba(34, 197, 94, 0.08)" },
  { border: "var(--color-warning)", bg: "rgba(234, 179, 8, 0.08)" },
  { border: "var(--color-danger)", bg: "rgba(239, 68, 68, 0.08)" },
];

/* ── Inline SVG Icons ─────────────────────────────────────────────── */

function GripIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="currentColor"
      className="shrink-0 opacity-40 group-hover:opacity-70 transition-opacity"
      aria-hidden="true"
    >
      <circle cx="5" cy="3" r="1.5" />
      <circle cx="11" cy="3" r="1.5" />
      <circle cx="5" cy="8" r="1.5" />
      <circle cx="11" cy="8" r="1.5" />
      <circle cx="5" cy="13" r="1.5" />
      <circle cx="11" cy="13" r="1.5" />
    </svg>
  );
}

function EyeIcon({ visible }: { visible: boolean }) {
  if (visible) {
    return (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    );
  }
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function MonitorIcon() {
  return (
    <svg
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className="text-text-muted mb-3 opacity-40"
      aria-hidden="true"
    >
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

/* ── Helpers ──────────────────────────────────────────────────────── */

function getSourceTypeBadge(type: string): { color: string; label: string } {
  const map: Record<string, { color: string; label: string }> = {
    video_capture_device: { color: "badge--info", label: "Video" },
    audio_input_capture: { color: "badge--accent", label: "Audio" },
    image_source: { color: "badge--brand", label: "Image" },
    text_gdiplus: { color: "badge--warning", label: "Text" },
    browser_source: { color: "badge--live", label: "Browser" },
    window_capture: { color: "badge--info", label: "Window" },
    display_capture: { color: "badge--danger", label: "Display" },
  };
  const hit = map[type];
  if (hit) return hit;
  const label = type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
  return { color: "badge--default", label };
}

/* ── Component ────────────────────────────────────────────────────── */

export function SceneSwitcher() {
  const [scenes, setScenes] = useState<string[]>([]);
  const [programScene, setProgramScene] = useState<string | null>(null);
  const [previewScene, setPreviewScene] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [taking, setTaking] = useState(false);
  const [takeFlash, setTakeFlash] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [transition, setTransition] = useState<TransitionType>("cut");
  const [transitionDuration, setTransitionDuration] = useState(500);
  const [expandedScene, setExpandedScene] = useState<string | null>(null);
  const [sceneSources, setSceneSources] = useState<Record<string, SceneSource[]>>({});
  const [sourcesLoading, setSourcesLoading] = useState<Record<string, boolean>>({});
  const [sourcesError, setSourcesError] = useState<Record<string, string | null>>({});
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const [transientError, setTransientError] = useState<string | null>(null);
  const errorTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* ── Transient error (auto-dismiss) ─────────────────────────────── */

  const showTransientError = useCallback((msg: string) => {
    setTransientError(msg);
    if (errorTimeoutRef.current) clearTimeout(errorTimeoutRef.current);
    errorTimeoutRef.current = setTimeout(() => setTransientError(null), 4000);
  }, []);

  /* ── Load scenes ────────────────────────────────────────────────── */

  const loadScenes = useCallback(async (initial = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getScenes();
      const savedOrder = localStorage.getItem("sceneOrder");
      let ordered: string[];
      if (savedOrder) {
        try {
          const parsed = JSON.parse(savedOrder) as string[];
          ordered = parsed.filter((s) => data.includes(s));
          for (const s of data) {
            if (!ordered.includes(s)) ordered.push(s);
          }
        } catch {
          ordered = data;
        }
      } else {
        ordered = data;
      }
      setScenes(ordered);
      if (ordered.length > 0 && initial) {
        setProgramScene(ordered[0]);
      }
    } catch {
      setError("OBS not connected");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadScenes(true);
  }, [loadScenes]);

  /* ── Fetch sources for a scene ──────────────────────────────────── */

  const fetchSources = useCallback(async (sceneName: string) => {
    setSourcesLoading((prev) => ({ ...prev, [sceneName]: true }));
    setSourcesError((prev) => ({ ...prev, [sceneName]: null }));
    try {
      const sources = await getSceneSources(sceneName);
      setSceneSources((prev) => ({ ...prev, [sceneName]: sources }));
    } catch {
      setSourcesError((prev) => ({ ...prev, [sceneName]: "Failed to load sources" }));
    }
    setSourcesLoading((prev) => ({ ...prev, [sceneName]: false }));
  }, []);

  /* ── Scene click (toggle source panel) ──────────────────────────── */

  const handleSceneClick = useCallback(
    (name: string) => {
      if (expandedScene === name) {
        setExpandedScene(null);
      } else {
        setExpandedScene(name);
        if (!sceneSources[name] && !sourcesLoading[name]) {
          fetchSources(name);
        }
      }
    },
    [expandedScene, sceneSources, sourcesLoading, fetchSources]
  );

  /* ── Toggle source visibility ───────────────────────────────────── */

  const handleToggleSource = useCallback(
    async (sceneName: string, sourceId: number) => {
      try {
        const result = await toggleSource(sceneName, sourceId);
        setSceneSources((prev) => {
          const sources = prev[sceneName];
          if (!sources) return prev;
          return {
            ...prev,
            [sceneName]: sources.map((s) =>
              s.id === sourceId ? { ...s, enabled: result.enabled } : s
            ),
          };
        });
      } catch {
        showTransientError("Failed to toggle source");
      }
    },
    [showTransientError]
  );

  /* ── Select preview ─────────────────────────────────────────────── */

  const handlePreview = useCallback(
    (name: string) => {
      if (name === programScene) return;
      setPreviewScene(name);
      setError(null);
    },
    [programScene]
  );

  /* ── Take ────────────────────────────────────────────────────────── */

  const handleTake = useCallback(async () => {
    if (!previewScene || previewScene === programScene || taking) return;
    setTaking(true);
    try {
      await switchScene(previewScene);
      setProgramScene(previewScene);
      setPreviewScene(null);
      setTakeFlash(true);
      setTimeout(() => setTakeFlash(false), 500);
      setError(null);
    } catch {
      showTransientError("Failed to take scene");
    }
    setTaking(false);
  }, [previewScene, programScene, taking, showTransientError]);

  /* ── Drag & drop reorder ────────────────────────────────────────── */

  const handleDragStart = (e: React.DragEvent, idx: number) => {
    setDraggedIdx(idx);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(idx));
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverIdx(idx);
  };

  const handleDragEnd = () => {
    if (draggedIdx !== null && dragOverIdx !== null && draggedIdx !== dragOverIdx) {
      setScenes((prev) => {
        const next = [...prev];
        const [moved] = next.splice(draggedIdx, 1);
        next.splice(dragOverIdx, 0, moved);
        localStorage.setItem("sceneOrder", JSON.stringify(next));
        return next;
      });
    }
    setDraggedIdx(null);
    setDragOverIdx(null);
  };

  /* ── Keyboard shortcuts ─────────────────────────────────────────── */

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      /* Ignore when user is typing in a form control */
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      let handled = false;

      /* 1-9: select scene at index as preview */
      const num = parseInt(e.key, 10);
      if (num >= 1 && num <= 9 && num <= scenes.length) {
        const name = scenes[num - 1];
        if (name !== programScene) {
          setPreviewScene(name);
          setError(null);
        }
        handled = true;
      }

      /* Enter / T: trigger Take */
      if (!handled && (e.key === "Enter" || e.key.toLowerCase() === "t")) {
        if (previewScene && previewScene !== programScene) {
          e.preventDefault();
          handleTake();
          handled = true;
        }
      }

      /* R: refresh scene list */
      if (!handled && e.key.toLowerCase() === "r") {
        e.preventDefault();
        loadScenes();
        handled = true;
      }

      /* Escape: clear preview and expanded panel */
      if (!handled && e.key === "Escape") {
        setPreviewScene(null);
        setExpandedScene(null);
        handled = true;
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [scenes, programScene, previewScene, handleTake, loadScenes]);

  /* ── Scene card renderer ─────────────────────────────────────────── */

  const renderSceneCard = (scene: string, idx: number) => {
    const isProgram = programScene === scene;
    const isPreview = previewScene === scene;
    const isExpanded = expandedScene === scene;
    const isDragged = draggedIdx === idx;
    const isOver = dragOverIdx === idx && dragOverIdx !== draggedIdx;
    const accent = CARD_ACCENTS[idx % CARD_ACCENTS.length];

    const sources = sceneSources[scene];
    const loadingSources = sourcesLoading[scene];
    const hasError = sourcesError[scene];

    return (
      <div
        key={scene}
        className={`flex flex-col gap-1.5 ${isDragged ? "opacity-40" : ""}`}
        style={{ transition: "opacity 0.15s ease" }}
      >
        {/* ── Scene Card ───────────────────────────────────────── */}
        <button
          draggable
          onDragStart={(e) => handleDragStart(e, idx)}
          onDragOver={(e) => handleDragOver(e, idx)}
          onDragEnd={handleDragEnd}
          onClick={() => handleSceneClick(scene)}
          onDoubleClick={() => handlePreview(scene)}
          className={[
            "group relative flex flex-col gap-1.5 w-full text-left rounded-lg border transition-all duration-150",
            "cursor-pointer p-3 min-h-[70px] select-none",
            /* PGM styling */
            isProgram
              ? "border-l-[3px] border-l-danger bg-danger/10 border-border text-text"
              : isPreview
                ? "border-l-[3px] border-l-live bg-live/10 border-border text-text"
                : "border-l-[3px] border-border",
            /* Drag-over indicator */
            isOver ? "ring-2 ring-brand ring-offset-1 ring-offset-bg-surface scale-[1.02]" : "",
            /* Interactions */
            "hover:shadow-elevated active:scale-[0.97]",
            isProgram
              ? "hover:bg-danger/15"
              : isPreview
                ? "hover:bg-live/15"
                : "hover:brightness-125",
            /* Take flash animation */
            takeFlash && isProgram ? "animate-[take-glow_0.5s_ease-out]" : "",
          ].join(" ")}
          style={
            !isProgram && !isPreview
              ? { borderLeftColor: accent.border, backgroundColor: accent.bg }
              : undefined
          }
          aria-label={`Scene: ${scene}${isProgram ? " (on air)" : ""}${isPreview ? " (preview)" : ""}`}
          aria-pressed={isExpanded}
        >
          {/* Drag handle + scene name row */}
          <div className="flex items-center gap-1.5">
            <span
              className="touch-none cursor-grab active:cursor-grabbing shrink-0"
              onMouseDown={(e) => e.stopPropagation()}
              aria-hidden="true"
            >
              <GripIcon />
            </span>
            <span className="font-semibold text-sm truncate flex-1">{scene}</span>
          </div>

          {/* Badges row */}
          <div className="flex items-center gap-1.5 flex-wrap min-h-[20px]">
            {isProgram && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-danger/20 text-danger border border-danger/30">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-danger animate-pulse" />
                ON AIR
              </span>
            )}
            {isPreview && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-live/20 text-live border border-live/30">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-live" />
                NEXT
              </span>
            )}
          </div>
        </button>

        {/* ── Expanded Source Panel ──────────────────────────────── */}
        {isExpanded && (
          <div className="rounded-lg border border-border bg-bg-elevated p-2.5 space-y-1 animate-fade-in-down">
            {/* Loading state */}
            {loadingSources && (
              <div className="flex items-center gap-2 py-1.5">
                <div className="w-3.5 h-3.5 border-2 border-brand border-t-transparent rounded-full animate-spin" />
                <span className="text-xs text-text-muted">Loading sources...</span>
              </div>
            )}

            {/* Error state */}
            {!loadingSources && hasError && (
              <div className="flex items-center justify-between py-0.5">
                <span className="text-xs text-danger">{hasError}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    fetchSources(scene);
                  }}
                  className="btn btn--sm btn-ghost text-xs"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Sources list */}
            {!loadingSources && !hasError && sources && sources.length > 0 && (
              <div className="space-y-0.5">
                {sources.map((src) => {
                  const b = getSourceTypeBadge(src.type);
                  return (
                    <div
                      key={src.id}
                      className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-bg-hover transition-colors"
                    >
                      <span className="flex-1 text-xs font-medium truncate text-text min-w-0">
                        {src.name}
                      </span>
                      <span className={`badge ${b.color} text-[9px] shrink-0`}>
                        {b.label}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleSource(scene, src.id);
                        }}
                        className={[
                          "p-1 rounded transition-colors shrink-0",
                          "focus-visible:outline-2 focus-visible:outline-brand",
                          src.enabled
                            ? "text-text-secondary hover:text-live hover:bg-live/10"
                            : "text-text-muted hover:text-text hover:bg-bg-hover",
                        ].join(" ")}
                        aria-label={src.enabled ? `Disable ${src.name}` : `Enable ${src.name}`}
                        title={src.enabled ? "Visible" : "Hidden"}
                      >
                        <EyeIcon visible={src.enabled} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Empty sources */}
            {!loadingSources && !hasError && sources && sources.length === 0 && (
              <p className="text-xs text-text-muted py-1.5 text-center">No sources in this scene</p>
            )}
          </div>
        )}
      </div>
    );
  };

  /* ────────────────────────────────────────────────────────────────── */
  /*  ERROR STATE  —  OBS disconnected, no scenes loaded                */
  /* ────────────────────────────────────────────────────────────────── */

  if (error && scenes.length === 0) {
    return (
      <div className="card space-y-4">
        <div className="section-header">
          <h3 className="section-header__title">Scenes</h3>
        </div>
        <div
          className="bg-accent-bg border border-warning/30 rounded-lg p-4 flex items-start gap-3 animate-fade-in"
          role="alert"
        >
          <span className="text-warning text-sm leading-none mt-0.5 font-bold shrink-0" aria-hidden="true">
            !
          </span>
          <div>
            <p className="text-warning text-sm font-semibold">OBS Disconnected</p>
            <p className="text-text-secondary text-xs mt-1">{error}</p>
            <button
              onClick={() => loadScenes()}
              className="btn btn-ghost btn--sm mt-3"
            >
              Retry Connection
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ────────────────────────────────────────────────────────────────── */
  /*  LOADING STATE  —  skeleton cards                                  */
  /* ────────────────────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="card space-y-4">
        <div className="section-header">
          <h3 className="section-header__title">Scenes</h3>
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2" aria-hidden="true">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex flex-col gap-1.5">
              <div className="h-[70px] bg-bg-elevated rounded-lg animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  /* ────────────────────────────────────────────────────────────────── */
  /*  MAIN RENDER                                                       */
  /* ────────────────────────────────────────────────────────────────── */

  const showShortcuts = scenes.length > 0;

  return (
    <div className="card space-y-4 scene-switcher" ref={undefined}>

      { /* Inline styles for custom animations and range input */ }
      <style>{`
        @keyframes take-glow {
          0%   { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6); }
          50%  { box-shadow: 0 0 24px 4px rgba(239, 68, 68, 0.3); }
          100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .scene-switcher input[type="range"] {
          -webkit-appearance: none;
          appearance: none;
          height: 6px;
          background: var(--color-bg-elevated);
          border-radius: 3px;
          outline: none;
          cursor: pointer;
        }
        .scene-switcher input[type="range"]::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: var(--color-brand);
          cursor: pointer;
          border: 2px solid var(--color-bg-surface);
        }
        .scene-switcher input[type="range"]::-moz-range-thumb {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: var(--color-brand);
          cursor: pointer;
          border: 2px solid var(--color-bg-surface);
        }
        .scene-switcher input[type="range"]:focus-visible {
          outline: 2px solid var(--color-brand);
          outline-offset: 2px;
        }
      `}</style>

      {/* ── Section Header ──────────────────────────────────────────── */}
      <div className="section-header">
        <div className="flex items-center gap-3">
          <h3 className="section-header__title">Scenes</h3>

          {/* Transition type selector */}
          <div
            className="flex rounded-lg border border-border overflow-hidden"
            role="radiogroup"
            aria-label="Transition type"
          >
            {TRANSITIONS.map((t) => (
              <button
                key={t.value}
                onClick={() => setTransition(t.value)}
                className={[
                  "px-3 py-1 text-xs font-medium transition-all",
                  transition === t.value
                    ? "bg-brand text-white"
                    : "bg-bg-elevated text-text-secondary hover:bg-bg-hover",
                ].join(" ")}
                role="radio"
                aria-checked={transition === t.value}
                aria-label={`${t.label} transition`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Bus indicators */}
        <div className="section-header__actions">
          <div className="flex items-center gap-3 text-xs">
            {programScene && (
              <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-danger/15 border border-danger/30">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-danger" />
                <span className="font-semibold text-danger uppercase tracking-wider text-[10px]">PGM</span>
                <span className="text-text font-mono font-medium">{programScene}</span>
              </span>
            )}
            {previewScene && (
              <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-live/15 border border-live/30">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-live" />
                <span className="font-semibold text-live uppercase tracking-wider text-[10px]">PVW</span>
                <span className="text-text font-mono font-medium">{previewScene}</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Empty state ──────────────────────────────────────────────── */}
      {scenes.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center animate-fade-in">
          <MonitorIcon />
          <p className="text-text-muted text-sm font-medium">No scenes available</p>
          <p className="text-text-muted text-xs mt-1 max-w-[240px]">
            Connect to OBS Studio to see your scene list here. Scenes can be switched, previewed, and
            managed from this panel.
          </p>
          <button onClick={() => loadScenes()} className="btn btn-ghost btn--sm mt-3">
            Refresh
          </button>
        </div>
      ) : (
        <>
          {/* ── Scene grid + Take button (side by side) ──────────────── */}
          <div className="flex items-end gap-3">
            <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2 items-start flex-1">
              {scenes.map((scene, idx) => renderSceneCard(scene, idx))}
            </div>

            <button
              onClick={handleTake}
              disabled={!previewScene || previewScene === programScene || taking}
              className={[
                "btn btn--lg px-6 shrink-0",
                "bg-accent text-white border-accent",
                "hover:bg-accent/80 active:bg-accent/60",
                "disabled:opacity-30 disabled:cursor-not-allowed",
                "font-semibold uppercase tracking-wider",
              ].join(" ")}
              aria-label="Take selected scene to program"
            >
              {taking ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                "Take"
              )}
            </button>
          </div>

          {/* ── Transition info + Duration slider ────────────────────── */}
          <div className="flex items-center gap-4 flex-wrap">
            {previewScene && previewScene !== programScene && (
              <div className="flex items-center gap-2 text-xs text-text-muted animate-fade-in">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  className="shrink-0"
                  aria-hidden="true"
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
                <span>
                  {transition === "cut"
                    ? `Cut to "${previewScene}" -- press Enter or click Take`
                    : `${transition === "mix" ? "Mix" : "Fade"} to "${previewScene}" -- ${transitionDuration}ms`}
                </span>
              </div>
            )}

            {/* Duration slider (right-aligned) */}
            {previewScene && previewScene !== programScene && (
              <div className="flex items-center gap-2 ml-auto">
                <label className="text-xs text-text-muted whitespace-nowrap">
                  Duration:{" "}
                  <span className="font-mono text-text-secondary">{transitionDuration}ms</span>
                </label>
                <input
                  type="range"
                  min={0}
                  max={2000}
                  step={50}
                  value={transitionDuration}
                  onChange={(e) => setTransitionDuration(Number(e.target.value))}
                  className="w-24"
                  aria-label="Transition duration in milliseconds"
                />
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Keyboard shortcuts hint ──────────────────────────────────── */}
      {showShortcuts && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-text-muted border-t border-border pt-3">
          <span className="text-text-muted/60 font-medium uppercase tracking-wider text-[9px]">
            Keys:
          </span>

          {scenes.slice(0, 9).map((_, i) => (
            <kbd
              key={i}
              className="px-1 py-0.5 rounded bg-bg-elevated border border-border text-text-secondary font-mono text-[10px] leading-none"
            >
              {i + 1}
            </kbd>
          ))}
          <span className="text-text-muted/50">preview</span>

          <kbd className="px-1 py-0.5 rounded bg-bg-elevated border border-border text-text-secondary font-mono text-[10px] leading-none">
            Enter
          </kbd>
          <span className="text-text-muted/50">Take</span>

          <kbd className="px-1 py-0.5 rounded bg-bg-elevated border border-border text-text-secondary font-mono text-[10px] leading-none">
            R
          </kbd>
          <span className="text-text-muted/50">Refresh</span>

          <kbd className="px-1 py-0.5 rounded bg-bg-elevated border border-border text-text-secondary font-mono text-[10px] leading-none">
            Esc
          </kbd>
          <span className="text-text-muted/50">Clear</span>
        </div>
      )}

      {/* ── Transient error banner (toast-style) ──────────────────────── */}
      {transientError && (
        <div
          className="bg-danger-bg border border-danger/40 rounded px-3 py-2.5 flex items-center gap-2 text-xs text-danger animate-fade-in-down"
          role="alert"
        >
          <span className="font-bold shrink-0" aria-hidden="true">
            !
          </span>
          <span className="flex-1">{transientError}</span>
          <button
            onClick={() => setTransientError(null)}
            className="text-text-muted hover:text-text-secondary ml-2 shrink-0"
            aria-label="Dismiss error"
          >
            Dismiss
          </button>
        </div>
      )}

    </div>
  );
}
