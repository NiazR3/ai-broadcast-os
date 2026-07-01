import { useState, useEffect, useRef, useCallback } from "react";
import { getDirectorStatus, generateDialogue, directorNext } from "../lib/api";
import type { DirectorStatus } from "../lib/api";

const SCROLL_SPEED_MIN = 1;
const SCROLL_SPEED_MAX = 20;
const SCROLL_SPEED_DEFAULT = 8;
const FONT_SIZE_MIN = 14;
const FONT_SIZE_MAX = 48;
const FONT_SIZE_DEFAULT = 20;

export function Teleprompter() {
  const [director, setDirector] = useState<DirectorStatus | null>(null);
  const [hostText, setHostText] = useState("");
  const [cohostText, setCohostText] = useState("");
  const [segmentTitle, setSegmentTitle] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(false);
  const [scrollSpeed, setScrollSpeed] = useState(SCROLL_SPEED_DEFAULT);
  const [fontSize, setFontSize] = useState(FONT_SIZE_DEFAULT);
  const [mirrorMode, setMirrorMode] = useState(false);
  const animFrameRef = useRef<number | null>(null);
  const lastTickRef = useRef<number>(0);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const d = await getDirectorStatus();
        setDirector(d);
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleNext = async () => {
    try {
      const result = await directorNext();
      setSegmentTitle(result.segment.title);
      // Auto-generate dialogue
      const d = await generateDialogue();
      setHostText(d.host.lines.map(l => l.text).join("\n\n"));
      setCohostText(d.cohost.lines.map(l => l.text).join("\n\n"));
      if (scrollRef.current) {
        scrollRef.current.scrollTop = 0;
      }
    } catch { /* ignore */ }
  };

  const handleRegenerate = async () => {
    try {
      const d = await generateDialogue();
      setHostText(d.host.lines.map(l => l.text).join("\n\n"));
      setCohostText(d.cohost.lines.map(l => l.text).join("\n\n"));
    } catch { /* ignore */ }
  };

  // Continuous auto-scroll using requestAnimationFrame
  const scrollTick = useCallback((timestamp: number) => {
    if (!autoScroll || !scrollRef.current) {
      animFrameRef.current = null;
      return;
    }

    if (lastTickRef.current === 0) {
      lastTickRef.current = timestamp;
    }

    const delta = timestamp - lastTickRef.current;
    lastTickRef.current = timestamp;

    // Speed: pixels per second = scrollSpeed * 4
    const pxPerMs = (scrollSpeed * 4) / 1000;
    const scrollDelta = delta * pxPerMs;

    const el = scrollRef.current;
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 2;

    if (atBottom) {
      // Auto-stop at the end
      setAutoScroll(false);
      animFrameRef.current = null;
      return;
    }

    el.scrollTop += scrollDelta;
    animFrameRef.current = requestAnimationFrame(scrollTick);
  }, [autoScroll, scrollSpeed]);

  useEffect(() => {
    if (autoScroll) {
      lastTickRef.current = 0;
      animFrameRef.current = requestAnimationFrame(scrollTick);
    } else {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }
    }

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [autoScroll, scrollTick]);

  const hasContent = hostText || cohostText;

  return (
    <div className="card flex flex-col min-h-[520px]">
      {/* Header */}
      <div className="section-header">
        <div className="flex items-center gap-3">
          <h3 className="section-header__title flex items-center gap-2">
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="flex items-center justify-center w-6 h-6 rounded text-text-muted hover:text-text hover:bg-bg-hover transition-all"
              aria-label={collapsed ? "Expand teleprompter" : "Collapse teleprompter"}
              aria-expanded={!collapsed}
            >
              <svg
                width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
                className={`transition-transform ${collapsed ? "-rotate-90" : ""}`}
                aria-hidden="true"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            Teleprompter
            {director?.running && (
              <span className="live-dot live-dot--sm" />
            )}
          </h3>
          {director && (
            <p className="section-header__subtitle mt-0.5">
              <span className="font-medium text-text-secondary">
                {director.script_title || "No script"}
              </span>
              <span className="text-text-muted mx-1">&middot;</span>
              <span className="text-text-muted">
                {segmentTitle || "No segment"}
              </span>
            </p>
          )}
        </div>
        <div className="section-header__actions">
          <button
            onClick={handleNext}
            className="btn btn-primary btn--sm"
          >
            Next Segment
          </button>
        </div>
      </div>

      {collapsed ? null : (
        <>
          {/* Teleprompter Text */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto pr-1 bg-bg-base rounded-lg p-5"
            style={{ maxHeight: "600px", minHeight: "280px" }}
            aria-live="polite"
          >
            {!hasContent ? (
              <div className="flex flex-col items-center justify-center h-40 gap-3">
                <svg className="w-10 h-10 text-text-muted/40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 6v6l4 2" />
                </svg>
                <p className="text-text-muted text-sm text-center">
                  Advance to a segment and generate dialogue
                </p>
              </div>
            ) : (
              <div className={`space-y-5 ${mirrorMode ? "scale-x-[-1]" : ""}`}>
                {hostText && (
                  <div className="border-l-2 border-brand pl-4 py-1.5">
                    <span className="badge badge--brand mb-2">Host</span>
                    <p className="leading-relaxed text-text" style={{ fontSize: `${fontSize}px` }}>{hostText}</p>
                  </div>
                )}
                {cohostText && (
                  <div className="border-l-2 border-accent pl-4 py-1.5">
                    <span className="badge badge--accent mb-2">Co-Host</span>
                    <p className="leading-relaxed text-text" style={{ fontSize: `${fontSize}px` }}>{cohostText}</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Controls */}
          {hasContent && (
            <div className="flex flex-wrap items-center gap-4 mt-4 pt-3 border-t border-border">
              {/* Left group: scroll controls */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleRegenerate}
                  className="btn btn-ghost btn--sm"
                >
                  Regenerate
                </button>
              </div>

              {/* Auto-scroll toggle + speed */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setAutoScroll(!autoScroll)}
                  className={`btn btn--sm ${autoScroll ? "bg-live text-bg-base border-live" : "btn-ghost"}`}
                  aria-pressed={autoScroll}
                  aria-label={autoScroll ? "Stop auto-scroll" : "Start auto-scroll"}
                >
                  {autoScroll ? (
                    <>
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-bg-base animate-pulse" />
                      Scrolling
                    </>
                  ) : (
                    <>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <polyline points="8 3 16 12 8 21" />
                      </svg>
                      Scroll
                    </>
                  )}
                </button>

                <label className="flex items-center gap-1.5 text-xs text-text-muted">
                  <span className="w-8 text-right">Speed</span>
                  <input
                    type="range"
                    min={SCROLL_SPEED_MIN}
                    max={SCROLL_SPEED_MAX}
                    value={scrollSpeed}
                    onChange={e => setScrollSpeed(Number(e.target.value))}
                    className="w-20 h-1.5 rounded-full appearance-none bg-border cursor-pointer accent-brand"
                    aria-label="Scroll speed"
                  />
                  <span className="w-4 text-center font-mono text-text-secondary">{scrollSpeed}</span>
                </label>
              </div>

              {/* Right group: display controls */}
              <div className="flex items-center gap-3 ml-auto">
                <label className="flex items-center gap-1.5 text-xs text-text-muted">
                  <span className="w-7">Size</span>
                  <input
                    type="range"
                    min={FONT_SIZE_MIN}
                    max={FONT_SIZE_MAX}
                    value={fontSize}
                    onChange={e => setFontSize(Number(e.target.value))}
                    className="w-16 h-1.5 rounded-full appearance-none bg-border cursor-pointer accent-brand"
                    aria-label="Font size"
                  />
                  <span className="w-6 text-center font-mono text-text-secondary">{Math.round(fontSize)}</span>
                </label>

                <button
                  onClick={() => setMirrorMode(!mirrorMode)}
                  className={`btn btn--sm ${mirrorMode ? "bg-brand/20 text-brand border-brand/40" : "btn-ghost"}`}
                  aria-pressed={mirrorMode}
                  aria-label="Toggle mirror mode for teleprompter glass"
                  title="Mirror mode (for teleprompter reflector glass)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="7 4 2 12 7 20" />
                    <polyline points="17 4 22 12 17 20" />
                  </svg>
                  Mirror
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
